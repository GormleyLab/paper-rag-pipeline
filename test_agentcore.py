#!/usr/bin/env python3
"""Test script for AgentCore MCP server."""

import base64
import json
import boto3

AGENT_ARN = "arn:aws:bedrock-agentcore:us-east-1:905723392067:runtime/paperrag-G5JW4e3Lc9"
REGION = "us-east-1"


def test_with_boto3():
    """Test AgentCore endpoint using boto3 client."""
    client = boto3.client('bedrock-agentcore', region_name=REGION)

    # MCP request - must be base64 encoded
    mcp_request = {"jsonrpc": "2.0", "method": "tools/list", "params": {}, "id": 1}
    payload = base64.b64encode(json.dumps(mcp_request).encode()).decode()

    try:
        response = client.invoke_agent_runtime(
            agentRuntimeArn=AGENT_ARN,
            qualifier="DEFAULT",
            contentType="application/json",
            accept="application/json, text/event-stream",
            payload=payload,
        )

        # Read the streaming response
        body = response['response'].read().decode('utf-8')
        print(f"Status: {response['statusCode']}")
        print(f"Content-Type: {response.get('contentType')}")
        print(f"Runtime Session ID: {response.get('runtimeSessionId')}")
        print(f"MCP Session ID: {response.get('mcpSessionId')}")
        print(f"\nRaw Response:\n{body[:500]}...")

        # Parse SSE format if present
        if body.startswith('event:'):
            print("\n--- Parsed SSE Response ---")
            for line in body.split('\n'):
                if line.startswith('data:'):
                    data = json.loads(line[5:].strip())
                    print(json.dumps(data, indent=2)[:1000])

        return response

    except Exception as e:
        print(f"Error: {e}")
        raise


def test_with_awscli():
    """Test AgentCore endpoint using AWS CLI (proven to work)."""
    import subprocess

    mcp_request = json.dumps({"jsonrpc": "2.0", "method": "tools/list", "params": {}, "id": 1})
    payload = base64.b64encode(mcp_request.encode()).decode()

    cmd = [
        "aws", "bedrock-agentcore", "invoke-agent-runtime",
        "--agent-runtime-arn", AGENT_ARN,
        "--qualifier", "DEFAULT",
        "--content-type", "application/json",
        "--accept", "application/json, text/event-stream",
        "--payload", payload,
        "--region", REGION,
        "output_test.json"
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    print(f"CLI Exit code: {result.returncode}")
    if result.returncode == 0:
        with open("output_test.json", "r") as f:
            response = f.read()
        print(f"Response (first 500 chars): {response[:500]}")
        if "tools" in response:
            print("\n✅ SUCCESS: MCP server returned tools list!")
            # Count tools
            tools_count = response.count('"name":')
            print(f"   Found {tools_count} tools")
    else:
        print(f"Error: {result.stderr}")


if __name__ == "__main__":
    print("=" * 60)
    print("Testing with AWS CLI (recommended method)")
    print("=" * 60)
    test_with_awscli()

    print("\n" + "=" * 60)
    print("Testing with boto3 (may have session handling differences)")
    print("=" * 60)
    test_with_boto3()
