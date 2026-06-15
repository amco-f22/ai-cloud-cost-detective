"""
AWS Scanner — Fetches cloud resources using AWS CLI subprocess calls.
Scans 10 resource categories in a given AWS region.
"""

import subprocess
import json
import logging

logger = logging.getLogger(__name__)


def _run_aws_cli(command: list[str]) -> dict | list | None:
    """Execute an AWS CLI command and return parsed JSON output."""
    try:
        result = subprocess.run(
            ["aws"] + command + ["--output", "json"],
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode != 0:
            logger.error(f"AWS CLI error: {result.stderr.strip()}")
            return None
        if not result.stdout.strip():
            return None
        return json.loads(result.stdout)
    except FileNotFoundError:
        raise RuntimeError(
            "AWS CLI is not installed. Install it from https://aws.amazon.com/cli/"
        )
    except subprocess.TimeoutExpired:
        logger.error(f"AWS CLI command timed out: {' '.join(command)}")
        return None
    except json.JSONDecodeError:
        logger.error(f"Failed to parse AWS CLI output for: {' '.join(command)}")
        return None


def get_regions() -> list[dict]:
    """Return list of available AWS regions."""
    data = _run_aws_cli(["ec2", "describe-regions"])
    if not data or "Regions" not in data:
        return []
    return [
        {
            "name": r["RegionName"],
            "endpoint": r.get("Endpoint", ""),
        }
        for r in data["Regions"]
    ]


def get_caller_identity() -> dict | None:
    """Verify AWS CLI is configured and return account info."""
    return _run_aws_cli(["sts", "get-caller-identity"])


def scan_ec2_instances(region: str) -> list[dict]:
    """Scan all EC2 instances in a region."""
    data = _run_aws_cli(
        ["ec2", "describe-instances", "--region", region]
    )
    if not data or "Reservations" not in data:
        return []
    instances = []
    for reservation in data["Reservations"]:
        for inst in reservation.get("Instances", []):
            name_tag = ""
            for tag in inst.get("Tags", []):
                if tag["Key"] == "Name":
                    name_tag = tag["Value"]
                    break
            instances.append({
                "type": "EC2 Instance",
                "id": inst["InstanceId"],
                "name": name_tag or inst["InstanceId"],
                "instance_type": inst.get("InstanceType", "unknown"),
                "state": inst.get("State", {}).get("Name", "unknown"),
                "launch_time": inst.get("LaunchTime", ""),
                "platform": inst.get("PlatformDetails", "Linux/UNIX"),
                "vpc_id": inst.get("VpcId", ""),
                "subnet_id": inst.get("SubnetId", ""),
                "public_ip": inst.get("PublicIpAddress", ""),
                "private_ip": inst.get("PrivateIpAddress", ""),
                "tags": inst.get("Tags", []),
                "region": region,
            })
    return instances


def scan_ebs_volumes(region: str) -> list[dict]:
    """Scan all EBS volumes in a region."""
    data = _run_aws_cli(
        ["ec2", "describe-volumes", "--region", region]
    )
    if not data or "Volumes" not in data:
        return []
    volumes = []
    for vol in data["Volumes"]:
        name_tag = ""
        for tag in vol.get("Tags", []):
            if tag["Key"] == "Name":
                name_tag = tag["Value"]
                break
        volumes.append({
            "type": "EBS Volume",
            "id": vol["VolumeId"],
            "name": name_tag or vol["VolumeId"],
            "size_gb": vol.get("Size", 0),
            "volume_type": vol.get("VolumeType", "unknown"),
            "state": vol.get("State", "unknown"),
            "iops": vol.get("Iops", 0),
            "throughput": vol.get("Throughput", 0),
            "encrypted": vol.get("Encrypted", False),
            "attachments": vol.get("Attachments", []),
            "tags": vol.get("Tags", []),
            "region": region,
        })
    return volumes


def scan_elastic_ips(region: str) -> list[dict]:
    """Scan all Elastic IPs in a region."""
    data = _run_aws_cli(
        ["ec2", "describe-addresses", "--region", region]
    )
    if not data or "Addresses" not in data:
        return []
    eips = []
    for addr in data["Addresses"]:
        name_tag = ""
        for tag in addr.get("Tags", []):
            if tag["Key"] == "Name":
                name_tag = tag["Value"]
                break
        eips.append({
            "type": "Elastic IP",
            "id": addr.get("AllocationId", ""),
            "name": name_tag or addr.get("PublicIp", ""),
            "public_ip": addr.get("PublicIp", ""),
            "association_id": addr.get("AssociationId", ""),
            "instance_id": addr.get("InstanceId", ""),
            "network_interface_id": addr.get("NetworkInterfaceId", ""),
            "domain": addr.get("Domain", ""),
            "tags": addr.get("Tags", []),
            "region": region,
        })
    return eips


def scan_security_groups(region: str) -> list[dict]:
    """Scan all Security Groups in a region."""
    data = _run_aws_cli(
        ["ec2", "describe-security-groups", "--region", region]
    )
    if not data or "SecurityGroups" not in data:
        return []
    sgs = []
    for sg in data["SecurityGroups"]:
        sgs.append({
            "type": "Security Group",
            "id": sg["GroupId"],
            "name": sg.get("GroupName", ""),
            "description": sg.get("Description", ""),
            "vpc_id": sg.get("VpcId", ""),
            "ingress_rules": sg.get("IpPermissions", []),
            "egress_rules": sg.get("IpPermissionsEgress", []),
            "tags": sg.get("Tags", []),
            "region": region,
        })
    return sgs


def scan_load_balancers(region: str) -> list[dict]:
    """Scan all ELBv2 load balancers (ALB/NLB) in a region."""
    data = _run_aws_cli(
        ["elbv2", "describe-load-balancers", "--region", region]
    )
    if not data or "LoadBalancers" not in data:
        return []

    lbs = []
    for lb in data["LoadBalancers"]:
        lb_arn = lb.get("LoadBalancerArn", "")
        # Fetch target groups for this LB
        target_groups = []
        tg_data = _run_aws_cli([
            "elbv2", "describe-target-groups",
            "--load-balancer-arn", lb_arn,
            "--region", region,
        ])
        if tg_data and "TargetGroups" in tg_data:
            for tg in tg_data["TargetGroups"]:
                # Check target health
                health_data = _run_aws_cli([
                    "elbv2", "describe-target-health",
                    "--target-group-arn", tg["TargetGroupArn"],
                    "--region", region,
                ])
                healthy_count = 0
                total_count = 0
                if health_data and "TargetHealthDescriptions" in health_data:
                    total_count = len(health_data["TargetHealthDescriptions"])
                    healthy_count = sum(
                        1 for t in health_data["TargetHealthDescriptions"]
                        if t.get("TargetHealth", {}).get("State") == "healthy"
                    )
                target_groups.append({
                    "arn": tg["TargetGroupArn"],
                    "name": tg.get("TargetGroupName", ""),
                    "healthy_count": healthy_count,
                    "total_count": total_count,
                })

        lbs.append({
            "type": "Load Balancer",
            "id": lb_arn,
            "name": lb.get("LoadBalancerName", ""),
            "lb_type": lb.get("Type", ""),
            "scheme": lb.get("Scheme", ""),
            "state": lb.get("State", {}).get("Code", "unknown"),
            "dns_name": lb.get("DNSName", ""),
            "vpc_id": lb.get("VpcId", ""),
            "target_groups": target_groups,
            "tags": [],
            "region": region,
        })
    return lbs


def scan_rds_instances(region: str) -> list[dict]:
    """Scan all RDS database instances in a region."""
    data = _run_aws_cli(
        ["rds", "describe-db-instances", "--region", region]
    )
    if not data or "DBInstances" not in data:
        return []
    instances = []
    for db in data["DBInstances"]:
        instances.append({
            "type": "RDS Instance",
            "id": db.get("DBInstanceIdentifier", ""),
            "name": db.get("DBInstanceIdentifier", ""),
            "engine": db.get("Engine", ""),
            "engine_version": db.get("EngineVersion", ""),
            "instance_class": db.get("DBInstanceClass", ""),
            "storage_gb": db.get("AllocatedStorage", 0),
            "storage_type": db.get("StorageType", ""),
            "multi_az": db.get("MultiAZ", False),
            "status": db.get("DBInstanceStatus", ""),
            "publicly_accessible": db.get("PubliclyAccessible", False),
            "backup_retention": db.get("BackupRetentionPeriod", 0),
            "tags": [],
            "region": region,
        })
    return instances


def scan_s3_buckets(region: str) -> list[dict]:
    """Scan S3 buckets (global service, filtered by region)."""
    data = _run_aws_cli(["s3api", "list-buckets"])
    if not data or "Buckets" not in data:
        return []

    buckets = []
    for bucket in data["Buckets"]:
        bucket_name = bucket["Name"]
        # Get bucket location to filter by region
        loc_data = _run_aws_cli([
            "s3api", "get-bucket-location",
            "--bucket", bucket_name,
        ])
        bucket_region = "us-east-1"  # default
        if loc_data and loc_data.get("LocationConstraint"):
            bucket_region = loc_data["LocationConstraint"]

        if bucket_region != region:
            continue

        # Check lifecycle configuration
        lifecycle = _run_aws_cli([
            "s3api", "get-bucket-lifecycle-configuration",
            "--bucket", bucket_name,
        ])
        has_lifecycle = lifecycle is not None and "Rules" in (lifecycle or {})

        # Check versioning
        versioning = _run_aws_cli([
            "s3api", "get-bucket-versioning",
            "--bucket", bucket_name,
        ])
        versioning_status = (versioning or {}).get("Status", "Disabled")

        buckets.append({
            "type": "S3 Bucket",
            "id": bucket_name,
            "name": bucket_name,
            "creation_date": bucket.get("CreationDate", ""),
            "region": bucket_region,
            "has_lifecycle_policy": has_lifecycle,
            "versioning": versioning_status,
            "tags": [],
        })
    return buckets


def scan_ebs_snapshots(region: str) -> list[dict]:
    """Scan EBS snapshots owned by the current account."""
    data = _run_aws_cli([
        "ec2", "describe-snapshots",
        "--owner-ids", "self",
        "--region", region,
    ])
    if not data or "Snapshots" not in data:
        return []
    snapshots = []
    for snap in data["Snapshots"]:
        name_tag = ""
        for tag in snap.get("Tags", []):
            if tag["Key"] == "Name":
                name_tag = tag["Value"]
                break
        snapshots.append({
            "type": "EBS Snapshot",
            "id": snap["SnapshotId"],
            "name": name_tag or snap["SnapshotId"],
            "volume_id": snap.get("VolumeId", ""),
            "size_gb": snap.get("VolumeSize", 0),
            "state": snap.get("State", ""),
            "start_time": snap.get("StartTime", ""),
            "description": snap.get("Description", ""),
            "encrypted": snap.get("Encrypted", False),
            "tags": snap.get("Tags", []),
            "region": region,
        })
    return snapshots


def scan_nat_gateways(region: str) -> list[dict]:
    """Scan NAT Gateways in a region."""
    data = _run_aws_cli(
        ["ec2", "describe-nat-gateways", "--region", region]
    )
    if not data or "NatGateways" not in data:
        return []
    nats = []
    for nat in data["NatGateways"]:
        name_tag = ""
        for tag in nat.get("Tags", []):
            if tag["Key"] == "Name":
                name_tag = tag["Value"]
                break
        nats.append({
            "type": "NAT Gateway",
            "id": nat["NatGatewayId"],
            "name": name_tag or nat["NatGatewayId"],
            "state": nat.get("State", ""),
            "vpc_id": nat.get("VpcId", ""),
            "subnet_id": nat.get("SubnetId", ""),
            "connectivity_type": nat.get("ConnectivityType", ""),
            "addresses": nat.get("NatGatewayAddresses", []),
            "tags": nat.get("Tags", []),
            "region": region,
        })
    return nats


def scan_lambda_functions(region: str) -> list[dict]:
    """Scan Lambda functions in a region."""
    data = _run_aws_cli(
        ["lambda", "list-functions", "--region", region]
    )
    if not data or "Functions" not in data:
        return []
    functions = []
    for fn in data["Functions"]:
        functions.append({
            "type": "Lambda Function",
            "id": fn.get("FunctionArn", ""),
            "name": fn.get("FunctionName", ""),
            "runtime": fn.get("Runtime", ""),
            "memory_mb": fn.get("MemorySize", 128),
            "timeout": fn.get("Timeout", 3),
            "code_size": fn.get("CodeSize", 0),
            "last_modified": fn.get("LastModified", ""),
            "handler": fn.get("Handler", ""),
            "tags": [],
            "region": region,
        })
    return functions


def scan_all_resources(region: str, progress_callback=None) -> dict:
    """
    Run all scanners for a given region and return aggregated results.
    Returns dict with resource lists and metadata.
    """
    identity = get_caller_identity()
    if not identity:
        raise RuntimeError(
            "AWS CLI is not configured. Run 'aws configure' first."
        )

    all_resources = []
    scan_results = {}

    scanners = [
        ("ec2_instances", scan_ec2_instances),
        ("ebs_volumes", scan_ebs_volumes),
        ("elastic_ips", scan_elastic_ips),
        ("security_groups", scan_security_groups),
        ("load_balancers", scan_load_balancers),
        ("rds_instances", scan_rds_instances),
        ("s3_buckets", scan_s3_buckets),
        ("ebs_snapshots", scan_ebs_snapshots),
        ("nat_gateways", scan_nat_gateways),
        ("lambda_functions", scan_lambda_functions),
    ]

    for name, scanner_fn in scanners:
        if progress_callback:
            progress_callback(f"Scanning {name.replace('_', ' ')}...")
        try:
            if name == "s3_buckets":
                resources = scanner_fn(region)
            else:
                resources = scanner_fn(region)
            scan_results[name] = resources
            all_resources.extend(resources)
            logger.info(f"Scanned {name}: {len(resources)} resources found")
        except Exception as e:
            logger.error(f"Error scanning {name}: {e}")
            scan_results[name] = []

    return {
        "region": region,
        "account_id": identity.get("Account", "unknown"),
        "total_resources": len(all_resources),
        "resources": all_resources,
        "breakdown": {k: len(v) for k, v in scan_results.items()},
    }
