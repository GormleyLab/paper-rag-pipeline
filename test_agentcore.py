#!/usr/bin/env python3
"""Test script for AgentCore MCP server."""

import base64
import json
import boto3

AGENT_ARN = "arn:aws:bedrock-agentcore:us-east-1:905723392067:runtime/paperrag-Y1TEct414w"
REGION = "us-east-1"


def test_with_boto3():
    """Test AgentCore endpoint using boto3 client."""
    client = boto3.client('bedrock-agentcore', region_name=REGION)

    # MCP request - must be base64 encoded
    mcp_request = {"jsonrpc": "2.0", "method": "tools/list", "id": 1}
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
        print(f"Runtime Session ID: {response.get('runtimeSessionId')}")
        print(f"Response: {body}")
        return response

    except Exception as e:
        print(f"Error: {e}")
        raise


if __name__ == "__main__":
    test_with_boto3()
