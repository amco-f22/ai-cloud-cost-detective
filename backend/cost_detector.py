"""
Cost Detector — Analyzes scanned AWS resources for 10 cost optimization categories.
Returns structured flags with severity and metadata for each detected issue.
"""

import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


def detect_all_cost_flags(scan_data: dict) -> list[dict]:
    """
    Run all detection checks against scanned resources.
    Returns a list of cost flag dicts with category, severity, resource info, and description.
    """
    flags = []
    resources = scan_data.get("resources", [])

    # Group resources by type for efficient processing
    by_type = {}
    for r in resources:
        rtype = r.get("type", "Unknown")
        by_type.setdefault(rtype, []).append(r)

    # Run each detector
    detectors = [
        _detect_oversized_ec2,
        _detect_unattached_ebs,
        _detect_old_snapshots,
        _detect_s3_no_lifecycle,
        _detect_unused_eips,
        _detect_permissive_security_groups,
        _detect_idle_rds,
        _detect_lb_no_healthy_targets,
        _detect_nat_gateways,
        _detect_oversized_ebs,
    ]

    for detector in detectors:
        try:
            detector_flags = detector(by_type)
            flags.extend(detector_flags)
        except Exception as e:
            logger.error(f"Error in detector {detector.__name__}: {e}")

    return flags


def _detect_oversized_ec2(by_type: dict) -> list[dict]:
    """Detect EC2 instances that may be oversized for their workload."""
    flags = []
    large_types = {
        "m5.xlarge", "m5.2xlarge", "m5.4xlarge", "m5.8xlarge", "m5.12xlarge",
        "m5.16xlarge", "m5.24xlarge",
        "m6i.xlarge", "m6i.2xlarge", "m6i.4xlarge", "m6i.8xlarge",
        "m6i.12xlarge", "m6i.16xlarge", "m6i.24xlarge",
        "c5.xlarge", "c5.2xlarge", "c5.4xlarge", "c5.9xlarge", "c5.18xlarge",
        "c6i.xlarge", "c6i.2xlarge", "c6i.4xlarge", "c6i.8xlarge",
        "r5.xlarge", "r5.2xlarge", "r5.4xlarge", "r5.8xlarge", "r5.12xlarge",
        "r6i.xlarge", "r6i.2xlarge", "r6i.4xlarge", "r6i.8xlarge",
        "t3.xlarge", "t3.2xlarge", "t3a.xlarge", "t3a.2xlarge",
        "m7i.xlarge", "m7i.2xlarge", "m7i.4xlarge", "m7i.8xlarge",
    }

    for inst in by_type.get("EC2 Instance", []):
        if inst.get("state") != "running":
            continue
        itype = inst.get("instance_type", "")
        if itype in large_types:
            flags.append({
                "category": "Oversized EC2 Instance",
                "severity": "high",
                "resource_type": "EC2 Instance",
                "resource_id": inst["id"],
                "resource_name": inst["name"],
                "current_config": f"Instance type: {itype}",
                "recommendation": f"Consider downsizing to a smaller instance type (e.g., t3.medium or t3.small) if CPU/memory utilization is low.",
                "estimated_savings": "$50–$500/month depending on instance type",
                "fix_command": f'aws ec2 stop-instances --instance-ids {inst["id"]} && aws ec2 modify-instance-attribute --instance-id {inst["id"]} --instance-type "{{\\\"Value\\\": \\\"t3.medium\\\"}}" && aws ec2 start-instances --instance-ids {inst["id"]}',
                "region": inst.get("region", ""),
            })

    return flags


def _detect_unattached_ebs(by_type: dict) -> list[dict]:
    """Detect EBS volumes not attached to any instance (orphan disks)."""
    flags = []
    for vol in by_type.get("EBS Volume", []):
        attachments = vol.get("attachments", [])
        if vol.get("state") == "available" and len(attachments) == 0:
            size = vol.get("size_gb", 0)
            vtype = vol.get("volume_type", "gp3")
            # Rough cost estimate
            monthly_cost = size * 0.08 if vtype == "gp2" else size * 0.08
            if vtype == "io1" or vtype == "io2":
                monthly_cost = size * 0.125

            flags.append({
                "category": "Unattached EBS Volume",
                "severity": "high",
                "resource_type": "EBS Volume",
                "resource_id": vol["id"],
                "resource_name": vol["name"],
                "current_config": f"{size} GB {vtype} volume — not attached to any instance",
                "recommendation": "Delete this orphaned volume or create a snapshot and delete it to stop charges.",
                "estimated_savings": f"~${monthly_cost:.0f}/month",
                "fix_command": f'aws ec2 delete-volume --volume-id {vol["id"]} --region {vol.get("region", "")}',
                "region": vol.get("region", ""),
            })

    return flags


def _detect_old_snapshots(by_type: dict) -> list[dict]:
    """Detect EBS snapshots older than 90 days."""
    flags = []
    now = datetime.now(timezone.utc)

    for snap in by_type.get("EBS Snapshot", []):
        start_time = snap.get("start_time", "")
        if not start_time:
            continue
        try:
            snap_date = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
            age_days = (now - snap_date).days
            if age_days > 90:
                size = snap.get("size_gb", 0)
                monthly_cost = size * 0.05  # ~$0.05/GB/month for snapshots

                flags.append({
                    "category": "Old EBS Snapshot",
                    "severity": "medium",
                    "resource_type": "EBS Snapshot",
                    "resource_id": snap["id"],
                    "resource_name": snap["name"],
                    "current_config": f"{size} GB snapshot, {age_days} days old",
                    "recommendation": f"This snapshot is {age_days} days old. Review if it's still needed and delete if not.",
                    "estimated_savings": f"~${monthly_cost:.0f}/month",
                    "fix_command": f'aws ec2 delete-snapshot --snapshot-id {snap["id"]} --region {snap.get("region", "")}',
                    "region": snap.get("region", ""),
                })
        except (ValueError, TypeError):
            continue

    return flags


def _detect_s3_no_lifecycle(by_type: dict) -> list[dict]:
    """Detect S3 buckets without lifecycle policies."""
    flags = []
    for bucket in by_type.get("S3 Bucket", []):
        if not bucket.get("has_lifecycle_policy", False):
            flags.append({
                "category": "S3 Bucket Without Lifecycle Policy",
                "severity": "medium",
                "resource_type": "S3 Bucket",
                "resource_id": bucket["id"],
                "resource_name": bucket["name"],
                "current_config": "No lifecycle policy configured",
                "recommendation": "Add a lifecycle policy to transition old objects to cheaper storage classes (Glacier, Intelligent-Tiering) or delete them automatically.",
                "estimated_savings": "10–40% on S3 storage costs",
                "fix_command": f'aws s3api put-bucket-lifecycle-configuration --bucket {bucket["name"]} --lifecycle-configuration \'{{"Rules": [{{"ID": "TransitionToIA", "Status": "Enabled", "Transitions": [{{"Days": 30, "StorageClass": "STANDARD_IA"}}, {{"Days": 90, "StorageClass": "GLACIER"}}], "Filter": {{}}}}]}}\'',
                "region": bucket.get("region", ""),
            })

    return flags


def _detect_unused_eips(by_type: dict) -> list[dict]:
    """Detect Elastic IPs not associated with any instance."""
    flags = []
    for eip in by_type.get("Elastic IP", []):
        if not eip.get("association_id") and not eip.get("instance_id"):
            flags.append({
                "category": "Unused Elastic IP",
                "severity": "low",
                "resource_type": "Elastic IP",
                "resource_id": eip["id"],
                "resource_name": eip.get("public_ip", eip["id"]),
                "current_config": f"Elastic IP {eip.get('public_ip', '')} — not associated with any resource",
                "recommendation": "Release this unused Elastic IP. AWS charges ~$3.65/month for unassociated EIPs.",
                "estimated_savings": "~$3.65/month",
                "fix_command": f'aws ec2 release-address --allocation-id {eip["id"]} --region {eip.get("region", "")}',
                "region": eip.get("region", ""),
            })

    return flags


def _detect_permissive_security_groups(by_type: dict) -> list[dict]:
    """Detect security groups with overly permissive ingress rules (0.0.0.0/0)."""
    flags = []
    sensitive_ports = {22, 3389, 3306, 5432, 1433, 27017, 6379, 9200, 8080, 8443}

    for sg in by_type.get("Security Group", []):
        for rule in sg.get("ingress_rules", []):
            for ip_range in rule.get("IpRanges", []):
                cidr = ip_range.get("CidrIp", "")
                if cidr == "0.0.0.0/0":
                    from_port = rule.get("FromPort", 0)
                    to_port = rule.get("ToPort", 65535)
                    protocol = rule.get("IpProtocol", "-1")

                    # Check if any sensitive port is in the range
                    is_sensitive = protocol == "-1" or any(
                        from_port <= p <= to_port for p in sensitive_ports
                    )

                    if is_sensitive:
                        port_desc = f"all traffic" if protocol == "-1" else f"ports {from_port}-{to_port}"
                        flags.append({
                            "category": "Overly Permissive Security Group",
                            "severity": "high",
                            "resource_type": "Security Group",
                            "resource_id": sg["id"],
                            "resource_name": sg["name"],
                            "current_config": f"Allows {port_desc} from 0.0.0.0/0 ({protocol})",
                            "recommendation": "Restrict access to specific IP ranges or use a VPN/bastion host instead of allowing public access.",
                            "estimated_savings": "Security risk — not direct cost but breach costs can be enormous",
                            "fix_command": f'aws ec2 revoke-security-group-ingress --group-id {sg["id"]} --protocol {protocol} --port {from_port} --cidr 0.0.0.0/0 --region {sg.get("region", "")}',
                            "region": sg.get("region", ""),
                        })
                        break  # One flag per SG is enough

    return flags


def _detect_idle_rds(by_type: dict) -> list[dict]:
    """Detect RDS instances that may be oversized or idle."""
    flags = []
    large_classes = {
        "db.m5.xlarge", "db.m5.2xlarge", "db.m5.4xlarge", "db.m5.8xlarge",
        "db.m6i.xlarge", "db.m6i.2xlarge", "db.m6i.4xlarge",
        "db.r5.xlarge", "db.r5.2xlarge", "db.r5.4xlarge",
        "db.r6i.xlarge", "db.r6i.2xlarge", "db.r6i.4xlarge",
        "db.m7g.xlarge", "db.m7g.2xlarge", "db.m7g.4xlarge",
    }

    for rds in by_type.get("RDS Instance", []):
        iclass = rds.get("instance_class", "")
        if iclass in large_classes:
            flags.append({
                "category": "Oversized RDS Instance",
                "severity": "high",
                "resource_type": "RDS Instance",
                "resource_id": rds["id"],
                "resource_name": rds["name"],
                "current_config": f"Instance class: {iclass}, Engine: {rds.get('engine', '')}, Storage: {rds.get('storage_gb', 0)} GB",
                "recommendation": f"Consider downsizing to db.t3.medium or db.t4g.medium if database utilization is low. Also check if Multi-AZ ({rds.get('multi_az')}) is needed.",
                "estimated_savings": "$100–$1000/month depending on instance class",
                "fix_command": f'aws rds modify-db-instance --db-instance-identifier {rds["id"]} --db-instance-class db.t3.medium --apply-immediately',
                "region": rds.get("region", ""),
            })

        # Check publicly accessible databases
        if rds.get("publicly_accessible", False):
            flags.append({
                "category": "Publicly Accessible RDS",
                "severity": "high",
                "resource_type": "RDS Instance",
                "resource_id": rds["id"],
                "resource_name": rds["name"],
                "current_config": f"RDS instance is publicly accessible",
                "recommendation": "Disable public access unless absolutely required. Use VPC peering or VPN for access.",
                "estimated_savings": "Security risk — not direct cost",
                "fix_command": f'aws rds modify-db-instance --db-instance-identifier {rds["id"]} --no-publicly-accessible --apply-immediately',
                "region": rds.get("region", ""),
            })

    return flags


def _detect_lb_no_healthy_targets(by_type: dict) -> list[dict]:
    """Detect load balancers without healthy backend targets."""
    flags = []
    for lb in by_type.get("Load Balancer", []):
        target_groups = lb.get("target_groups", [])
        if not target_groups:
            flags.append({
                "category": "Load Balancer Without Targets",
                "severity": "medium",
                "resource_type": "Load Balancer",
                "resource_id": lb["id"],
                "resource_name": lb["name"],
                "current_config": f"{lb.get('lb_type', 'application')} load balancer with no target groups",
                "recommendation": "Delete this load balancer if it has no backends. ALBs cost ~$16/month + LCU charges even with no traffic.",
                "estimated_savings": "~$16–$30/month",
                "fix_command": f'aws elbv2 delete-load-balancer --load-balancer-arn {lb["id"]} --region {lb.get("region", "")}',
                "region": lb.get("region", ""),
            })
        else:
            # Check if all targets are unhealthy
            all_unhealthy = all(
                tg.get("healthy_count", 0) == 0 and tg.get("total_count", 0) > 0
                for tg in target_groups
            )
            no_targets = all(tg.get("total_count", 0) == 0 for tg in target_groups)

            if all_unhealthy or no_targets:
                status = "all targets unhealthy" if all_unhealthy else "no registered targets"
                flags.append({
                    "category": "Load Balancer Without Healthy Targets",
                    "severity": "medium",
                    "resource_type": "Load Balancer",
                    "resource_id": lb["id"],
                    "resource_name": lb["name"],
                    "current_config": f"{lb.get('lb_type', 'application')} LB — {status}",
                    "recommendation": "Fix target health or delete the load balancer to stop charges.",
                    "estimated_savings": "~$16–$30/month",
                    "fix_command": f'aws elbv2 delete-load-balancer --load-balancer-arn {lb["id"]} --region {lb.get("region", "")}',
                    "region": lb.get("region", ""),
                })

    return flags


def _detect_nat_gateways(by_type: dict) -> list[dict]:
    """Detect NAT Gateways that may be unnecessary (cost ~$32/month + data)."""
    flags = []
    for nat in by_type.get("NAT Gateway", []):
        if nat.get("state") == "available":
            flags.append({
                "category": "NAT Gateway Cost Review",
                "severity": "medium",
                "resource_type": "NAT Gateway",
                "resource_id": nat["id"],
                "resource_name": nat["name"],
                "current_config": f"NAT Gateway in VPC {nat.get('vpc_id', '')} — costs ~$32/month + $0.045/GB data",
                "recommendation": "Review if this NAT Gateway is actively used. Consider using VPC endpoints for AWS services to reduce NAT traffic, or consolidate NAT Gateways across AZs.",
                "estimated_savings": "$32–$100+/month",
                "fix_command": f'aws ec2 delete-nat-gateway --nat-gateway-id {nat["id"]} --region {nat.get("region", "")}',
                "region": nat.get("region", ""),
            })

    return flags


def _detect_oversized_ebs(by_type: dict) -> list[dict]:
    """Detect oversized EBS volumes (large volumes that may be underutilized)."""
    flags = []
    for vol in by_type.get("EBS Volume", []):
        size = vol.get("size_gb", 0)
        vtype = vol.get("volume_type", "")
        attachments = vol.get("attachments", [])

        # Flag large io1/io2 volumes (expensive IOPS-provisioned storage)
        if vtype in ("io1", "io2") and size > 100:
            iops = vol.get("iops", 0)
            flags.append({
                "category": "Oversized Provisioned IOPS Volume",
                "severity": "high",
                "resource_type": "EBS Volume",
                "resource_id": vol["id"],
                "resource_name": vol["name"],
                "current_config": f"{size} GB {vtype} volume with {iops} IOPS",
                "recommendation": f"Review if provisioned IOPS is needed. Consider switching to gp3 which includes 3000 IOPS free. gp3 costs ~$0.08/GB vs io1 at ~$0.125/GB + $0.065/IOPS.",
                "estimated_savings": f"${(size * 0.045) + (iops * 0.065):.0f}/month",
                "fix_command": f'aws ec2 modify-volume --volume-id {vol["id"]} --volume-type gp3 --region {vol.get("region", "")}',
                "region": vol.get("region", ""),
            })
        # Flag very large gp2/gp3 volumes
        elif size >= 500 and len(attachments) > 0:
            flags.append({
                "category": "Large EBS Volume Review",
                "severity": "low",
                "resource_type": "EBS Volume",
                "resource_id": vol["id"],
                "resource_name": vol["name"],
                "current_config": f"{size} GB {vtype} volume",
                "recommendation": "Review if the full volume size is utilized. Consider reducing size or archiving old data to S3.",
                "estimated_savings": "Varies based on utilization",
                "fix_command": "# Manual review recommended — check disk utilization via CloudWatch or SSH",
                "region": vol.get("region", ""),
            })

    return flags
