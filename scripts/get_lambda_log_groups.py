import argparse
import json
import subprocess


def _aws_command(base_args, region=None):
    command = ["aws", *base_args]
    if region:
        command.extend(["--region", region])
    return command


def _run_aws_cli(command):
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        stderr = result.stderr.strip() or "Unknown AWS CLI error."
        raise RuntimeError(f"AWS CLI command failed: {stderr}")
    return json.loads(result.stdout or "{}")


def _list_lambda_resources(stack_name, region=None):
    command = _aws_command(
        ["cloudformation", "describe-stack-resources", "--stack-name", stack_name],
        region=region,
    )
    payload = _run_aws_cli(command)
    resources = payload.get("StackResources", [])
    return [
        resource
        for resource in resources
        if resource.get("ResourceType") == "AWS::Lambda::Function"
    ]


def main():
    parser = argparse.ArgumentParser(description="List Lambda log groups for one CloudFormation stack.")
    parser.add_argument("--stack-name", required=True, help="CloudFormation stack name.")
    parser.add_argument("--region", help="AWS region override, for example ap-southeast-1.")
    args = parser.parse_args()

    resources = _list_lambda_resources(args.stack_name, region=args.region)
    if not resources:
        print(f"No Lambda functions found in stack {args.stack_name}.")
        return

    print("logical_id | function_name | log_group_name")
    print("-----------+---------------+----------------")
    for resource in resources:
        logical_id = resource.get("LogicalResourceId", "-")
        function_name = resource.get("PhysicalResourceId", "-")
        log_group_name = f"/aws/lambda/{function_name}" if function_name != "-" else "-"
        print(f"{logical_id} | {function_name} | {log_group_name}")


if __name__ == "__main__":
    main()