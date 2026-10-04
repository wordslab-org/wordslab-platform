"""The canary's OpenAPI fragment — the capability's API self-description.

The fragment uses the FULL contract paths (`/v1/...`) and is merged into the
service's document by `contract.base.openapi.openapi_document`; the `/mcp`
tools are then auto-generated from the merged document. Authoring rule:
describe the API the way a client drives it — schema per request body,
`operationId` per operation (it becomes the MCP tool's name).
"""

from __future__ import annotations

openapi_fragment = {
    "paths": {
        "/v1/echo": {
            "post": {
                "operationId": "echo",
                "summary": "Echo the request body back.",
                "description": "Returns the JSON object received, unchanged.",
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "additionalProperties": True,
                            }
                        }
                    },
                },
                "responses": {
                    "200": {
                        "description": "The echoed request body.",
                        "content": {
                            "application/json": {
                                "schema": {"type": "object", "additionalProperties": True}
                            }
                        },
                    }
                },
            }
        },
        "/v1/echo/ping": {
            "get": {
                "operationId": "echo.ping",
                "summary": "Ping the canary.",
                "description": "Returns pong — a liveness probe for the canary capability.",
                "responses": {
                    "200": {
                        "description": "Pong.",
                        "content": {
                            "application/json": {"schema": {"type": "object", "required": ["pong"], "properties": {"pong": {"type": "boolean"}}}}
                        },
                    }
                },
            }
        },
    }
}
