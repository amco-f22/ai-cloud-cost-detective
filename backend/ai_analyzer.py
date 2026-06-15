"""
AI Analyzer — Sends scanned resources + detection flags to an AI model
for deep cost analysis and actionable recommendations.
Supports: Google Gemini (default), Groq
"""

import json
import os
import time
import logging
import httpx

logger = logging.getLogger(__name__)

# ─── Provider configs ───
GEMINI_API_BASE = "https://generativelanguage.googleapis.com/v1beta"
GROQ_API_BASE = "https://api.groq.com/openai/v1"

GEMINI_FALLBACKS = ["gemini-2.5-flash"]
GROQ_FALLBACKS = ["llama-3.3-70b-versatile", "llama-3.1-8b-instant"]

MAX_RETRIES = 3
RETRY_BACKOFF_BASE = 2  # seconds — retries at 2s, 4s, 8s

SYSTEM_PROMPT = """You are an expert AWS Cloud Cost Optimization Consultant.

You will receive:
1. A list of AWS resources with EXACT configuration data scanned from a live AWS account
2. Pre-detected cost flags/issues found by automated rule-based analysis

CRITICAL RULES — YOU MUST FOLLOW THESE:
- ONLY use data that is explicitly provided in the input. NEVER fabricate or assume resource details.
- Use the EXACT instance_type, size_gb, volume_type, state, and attachments values from the data.
- If an EBS volume has "attachments" that is a non-empty list, it IS attached — do NOT flag it as unused.
- If an EC2 instance_type is "t2.micro", report it as "t2.micro" — do NOT change it to a different type.
- Do NOT claim a resource is "over-provisioned" unless you have utilization metrics (you don't). Instead, suggest monitoring with CloudWatch.
- For pre-detected flags: validate them against the raw data. If the data contradicts a flag, REMOVE it.
- Use the actual resource_id, resource_name, instance_type, and size values from the provided data in your response.

Your job is to:
1. Validate pre-detected flags against the actual resource data (remove false positives)
2. Check for security misconfigurations (open security groups, public access)
3. Check for unused/orphaned resources (unattached EBS where attachments=[], unused EIPs)
4. Check for missing best practices (no lifecycle policies, no encryption, no backups)
5. Suggest cost optimization strategies (Reserved Instances, Savings Plans, Spot for dev/test)
6. Provide specific, actionable AWS CLI commands for each recommendation

RESPONSE FORMAT (strict JSON):
{
  "summary": "Write a highly detailed, 3-4 sentence paragraph summarizing the exact findings. Explicitly mention resource counts, specific issues found (e.g. 'All EC2 instances are stopped but their EBS volumes are incurring costs', '6 security groups expose administrative ports'), and the overall impact.",
  "total_resources_scanned": <int>,
  "total_issues_found": <int>,
  "estimated_monthly_savings": "$X-$Y",
  "issues": [
    {
      "title": "Issue title",
      "resource_type": "EC2 Instance | EBS Volume | S3 Bucket | ...",
      "resource_id": "exact-resource-id-from-data",
      "resource_name": "exact-name-from-data",
      "severity": "high | medium | low",
      "category": "unused | misconfigured | security-risk | optimization",
      "current_state": "EXACT current config from the data provided",
      "recommendation": "What should be done",
      "fix_command": "aws cli command to fix",
      "estimated_savings": "$X/month",
      "additional_notes": "Any extra context"
    }
  ],
  "additional_recommendations": [
    "Write 3-5 specific, detailed recommendations tailored to the EXACT resources provided in the data. Do NOT use generic advice. Reference specific resource IDs or types that were scanned."
  ]
    "General best-practice recommendations not tied to a specific resource"
  ]
}

IMPORTANT:
- Always respond with valid JSON only, no markdown, no code fences
- NEVER invent instance types, volume sizes, or resource states that aren't in the data
- Include actual AWS CLI commands that can be copy-pasted and run
- Be conservative with savings estimates
- If there are few or no issues, say so honestly — do NOT invent problems
"""


# ─── Gemini REST API ───

def _call_gemini(model: str, api_key: str, user_prompt: str) -> dict | None:
    """Call Gemini REST API with retries."""
    url = f"{GEMINI_API_BASE}/models/{model}:generateContent"
    headers = {"Content-Type": "application/json", "x-goog-api-key": api_key}
    payload = {
        "system_instruction": {"parts": [{"text": SYSTEM_PROMPT}]},
        "contents": [{"role": "user", "parts": [{"text": user_prompt}]}],
        "generationConfig": {
            "temperature": 0.2,
            "maxOutputTokens": 8192,
            "responseMimeType": "application/json",
        },
    }

    for attempt in range(MAX_RETRIES):
        try:
            with httpx.Client(timeout=120.0) as client:
                resp = client.post(url, json=payload, headers=headers)
            if resp.status_code == 200:
                candidates = resp.json().get("candidates", [])
                if candidates:
                    text = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                    
                    # Robust JSON extraction (like Groq)
                    start = text.find("{")
                    end = text.rfind("}") + 1
                    if start >= 0 and end > start:
                        return json.loads(text[start:end])
                    logger.error(f"Gemini {model}: no JSON found in response")
                    return None
            if resp.status_code in (503, 429):
                wait = RETRY_BACKOFF_BASE * (2 ** attempt)
                logger.warning(f"Gemini {model}: {resp.status_code}, retry in {wait}s...")
                time.sleep(wait)
                continue
            logger.error(f"Gemini {model}: {resp.status_code} — {resp.text[:200]}")
            return None
        except (httpx.TimeoutException, json.JSONDecodeError) as e:
            wait = RETRY_BACKOFF_BASE * (2 ** attempt)
            logger.warning(f"Gemini {model}: {e}, retry in {wait}s...")
            time.sleep(wait)
        except Exception as e:
            logger.error(f"Gemini {model}: unexpected — {e}")
            return None
    return None


# ─── Groq REST API (OpenAI-compatible) ───

def _call_groq(model: str, api_key: str, user_prompt: str) -> dict | None:
    """Call Groq API (OpenAI-compatible) with retries."""
    url = f"{GROQ_API_BASE}/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT + "\n\nDo NOT wrap your response in markdown code fences. Output raw JSON only."},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.2,
        "max_tokens": 4096,
    }

    for attempt in range(MAX_RETRIES):
        try:
            with httpx.Client(timeout=120.0) as client:
                resp = client.post(url, json=payload, headers=headers)
            if resp.status_code == 200:
                content = resp.json()["choices"][0]["message"]["content"]
                # Strip markdown fences or thinking tags if present
                content = content.strip()
                if content.startswith("```"):
                    content = content.split("\n", 1)[1] if "\n" in content else content[3:]
                    if content.endswith("```"):
                        content = content[:-3]
                    content = content.strip()
                # Remove <think>...</think> tags (Qwen3 reasoning)
                import re
                content = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL).strip()
                # Find the JSON object
                start = content.find("{")
                end = content.rfind("}") + 1
                if start >= 0 and end > start:
                    return json.loads(content[start:end])
                logger.error(f"Groq {model}: no JSON found in response")
                return None
            if resp.status_code in (503, 429):
                wait = RETRY_BACKOFF_BASE * (2 ** attempt)
                logger.warning(f"Groq {model}: {resp.status_code}, retry in {wait}s...")
                time.sleep(wait)
                continue
            logger.error(f"Groq {model}: {resp.status_code} -- {resp.text[:200]}")
            return None
        except (httpx.TimeoutException, json.JSONDecodeError) as e:
            wait = RETRY_BACKOFF_BASE * (2 ** attempt)
            logger.warning(f"Groq {model}: {e}, retry in {wait}s...")
            time.sleep(wait)
        except Exception as e:
            logger.error(f"Groq {model}: unexpected -- {e}")
            return None
    return None


def _build_compact_resources(scan_data: dict) -> str:
    """Build a compact resource summary for providers with low token limits (Groq)."""
    lines = []
    for res in scan_data.get("resources", []):
        # Keep only essential fields
        compact = {
            "type": res.get("type", res.get("resource_type", "unknown")),
            "id": res.get("id", res.get("resource_id", "")),
            "name": res.get("name", res.get("resource_name", "")),
        }
        # Add size/state info if present
        for key in ["InstanceType", "State", "Size", "StorageClass", "Engine", "DBInstanceClass"]:
            if key in res:
                compact[key] = res[key]
        lines.append(json.dumps(compact, default=str))
    return "\n".join(lines)


def _build_compact_flags(cost_flags: list[dict]) -> str:
    """Build compact cost flags summary."""
    lines = []
    for flag in cost_flags:
        compact = {
            "category": flag.get("category", ""),
            "resource": flag.get("resource_name", flag.get("resource_id", "")),
            "severity": flag.get("severity", ""),
            "recommendation": flag.get("recommendation", ""),
        }
        lines.append(json.dumps(compact, default=str))
    return "\n".join(lines)


def analyze_costs(scan_data: dict, cost_flags: list[dict]) -> dict:
    """
    Send scanned resources and detection flags to an AI model for deep analysis.
    Supports Gemini and Groq. Set AI_PROVIDER in .env to switch.
    """
    provider = os.getenv("AI_PROVIDER", "gemini").lower()

    # Build prompt — compact for Groq (low TPM limits), full for Gemini
    if provider == "groq":
        user_prompt = f"""Analyze AWS resources in region '{scan_data.get("region", "unknown")}' (Account: {scan_data.get("account_id", "unknown")}):

Resources ({scan_data.get("total_resources", 0)} total):
{_build_compact_resources(scan_data)}

Pre-Detected Issues ({len(cost_flags)} flags):
{_build_compact_flags(cost_flags)}

Analyze all resources, validate issues, find additional optimizations, and provide fix commands.
"""
    else:
        user_prompt = f"""Analyze the following AWS resources in region '{scan_data.get("region", "unknown")}' 
(Account: {scan_data.get("account_id", "unknown")}):

## Resources Scanned ({scan_data.get("total_resources", 0)} total)

Resource breakdown:
{json.dumps(scan_data.get("breakdown", {}), indent=2)}

## Full Resource Details
{json.dumps(scan_data.get("resources", []), indent=2, default=str)}

## Pre-Detected Cost Issues ({len(cost_flags)} flags)
{json.dumps(cost_flags, indent=2, default=str)}

Please analyze all resources comprehensively, validate the pre-detected issues,
find any additional optimization opportunities, and provide actionable fix commands.
"""

    result = None

    if provider == "groq":
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise RuntimeError("GROQ_API_KEY not set in .env")
        primary = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
        models = [primary] + [m for m in GROQ_FALLBACKS if m != primary]
        caller = _call_groq
    else:  # gemini (default)
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise RuntimeError("GOOGLE_API_KEY not set in .env")
        primary = os.getenv("GEMINI_MODEL", "gemini-3.5-flash")
        models = [primary] + [m for m in GEMINI_FALLBACKS if m != primary]
        caller = _call_gemini

    # Try primary model, then fallbacks
    for model in models:
        logger.info(f"Trying {provider}/{model}...")
        result = caller(model, api_key, user_prompt)
        if result is not None:
            if model != models[0]:
                logger.info(f"Used fallback {model} instead of {models[0]}")
            break
        logger.warning(f"{provider}/{model} failed, trying next...")

    if result is None:
        logger.error(f"All {provider} models failed. Returning automated detection only.")
        return _build_fallback_response(scan_data, cost_flags)

    # Ensure required fields
    result.setdefault("summary", "Analysis complete")
    result.setdefault("total_resources_scanned", scan_data.get("total_resources", 0))
    result.setdefault("total_issues_found", len(result.get("issues", [])))
    result.setdefault("estimated_monthly_savings", "Unable to estimate")
    result.setdefault("issues", [])
    result.setdefault("additional_recommendations", [])

    logger.info(
        f"AI analysis complete ({provider}): "
        f"{result['total_issues_found']} issues, "
        f"savings: {result['estimated_monthly_savings']}"
    )
    return result


def _build_fallback_response(scan_data: dict, cost_flags: list[dict]) -> dict:
    """Build a response from pre-detected cost flags when AI is unavailable."""
    return {
        "summary": "AI analysis was unavailable. Showing results from automated detection only.",
        "total_resources_scanned": scan_data.get("total_resources", 0),
        "total_issues_found": len(cost_flags),
        "estimated_monthly_savings": "See individual issues",
        "issues": [
            {
                "title": flag.get("category", "Issue"),
                "resource_type": flag.get("resource_type", "Unknown"),
                "resource_id": flag.get("resource_id", ""),
                "resource_name": flag.get("resource_name", ""),
                "severity": flag.get("severity", "medium"),
                "category": flag.get("category", ""),
                "current_state": flag.get("current_config", ""),
                "recommendation": flag.get("recommendation", ""),
                "fix_command": flag.get("fix_command", ""),
                "estimated_savings": flag.get("estimated_savings", ""),
                "additional_notes": "Based on automated detection (AI unavailable)",
            }
            for flag in cost_flags
        ],
        "additional_recommendations": [
            "AI analysis was temporarily unavailable. Re-run later for deeper insights.",
        ],
    }
