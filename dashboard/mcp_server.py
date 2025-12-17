#!/usr/bin/env python3
"""
Streamlit Component Manifest MCP Server

This MCP server exposes the trading dashboard's component manifest to AI agents,
enabling them to generate consistent, high-quality UI code following established
patterns and design tokens.

Based on the Storybook MCP concept: provide curated, machine-readable context
rather than dumping entire codebases.

Usage:
    python dashboard/mcp_server.py [--port 8765]

Then configure Claude Code:
    claude mcp add trading-ui --transport http http://localhost:8765/mcp --scope project
"""

import argparse
import json
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn

# Load manifest
MANIFEST_PATH = Path(__file__).parent / "component_manifest.json"

app = FastAPI(
    title="Trading Dashboard MCP Server",
    description="Exposes component manifest for AI-assisted UI development",
    version="1.0.0",
)

# Enable CORS for MCP clients
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def load_manifest() -> dict:
    """Load the component manifest."""
    if MANIFEST_PATH.exists():
        with open(MANIFEST_PATH) as f:
            return json.load(f)
    return {"error": "Manifest not found"}


@app.get("/")
async def root():
    """Health check endpoint."""
    return {"status": "ok", "service": "Trading Dashboard MCP Server"}


@app.get("/mcp")
@app.post("/mcp")
async def mcp_endpoint(request: Request):
    """
    MCP protocol endpoint.

    Supports the Model Context Protocol for serving component metadata
    to AI coding agents like Claude Code.
    """
    manifest = load_manifest()

    # Handle MCP discovery
    if request.method == "GET":
        return JSONResponse({
            "name": "trading-ui-components",
            "version": "1.0.0",
            "description": "Trading dashboard component manifest for AI-assisted development",
            "capabilities": {
                "tools": True,
                "resources": True,
            },
            "tools": [
                {
                    "name": "get_design_tokens",
                    "description": "Get all design tokens (colors, gradients, typography, spacing)",
                },
                {
                    "name": "get_component",
                    "description": "Get detailed info about a specific component",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "name": {
                                "type": "string",
                                "description": "Component name (e.g., 'heroMetric', 'sentimentGauge')"
                            }
                        },
                        "required": ["name"]
                    }
                },
                {
                    "name": "list_components",
                    "description": "List all available components with brief descriptions",
                },
                {
                    "name": "get_patterns",
                    "description": "Get common code patterns and conventions",
                },
                {
                    "name": "get_full_manifest",
                    "description": "Get the complete component manifest",
                },
            ]
        })

    # Handle MCP tool calls (POST)
    try:
        body = await request.json()
        tool_name = body.get("tool")
        params = body.get("parameters", {})

        if tool_name == "get_design_tokens":
            return JSONResponse({
                "result": manifest.get("designTokens", {}),
                "usage": "Use these tokens for consistent styling across all UI components"
            })

        elif tool_name == "get_component":
            component_name = params.get("name")
            components = manifest.get("components", {})
            if component_name in components:
                return JSONResponse({
                    "result": components[component_name],
                    "usage": f"Use this component for {components[component_name].get('description', 'UI element')}"
                })
            return JSONResponse({
                "error": f"Component '{component_name}' not found",
                "available": list(components.keys())
            }, status_code=404)

        elif tool_name == "list_components":
            components = manifest.get("components", {})
            summary = {
                name: {
                    "description": comp.get("description"),
                    "file": comp.get("file"),
                    "function": comp.get("function")
                }
                for name, comp in components.items()
            }
            return JSONResponse({"result": summary})

        elif tool_name == "get_patterns":
            return JSONResponse({
                "patterns": manifest.get("patterns", {}),
                "conventions": manifest.get("conventions", {}),
                "utilities": manifest.get("utilities", {})
            })

        elif tool_name == "get_full_manifest":
            return JSONResponse({"result": manifest})

        else:
            return JSONResponse({
                "error": f"Unknown tool: {tool_name}",
                "available_tools": [
                    "get_design_tokens",
                    "get_component",
                    "list_components",
                    "get_patterns",
                    "get_full_manifest"
                ]
            }, status_code=400)

    except json.JSONDecodeError:
        return JSONResponse({"error": "Invalid JSON in request body"}, status_code=400)


@app.get("/manifest")
async def get_manifest():
    """Direct access to the full manifest."""
    return JSONResponse(load_manifest())


@app.get("/components")
async def list_components():
    """List all components with their descriptions."""
    manifest = load_manifest()
    components = manifest.get("components", {})
    return JSONResponse({
        name: {
            "description": comp.get("description"),
            "props": list(comp.get("props", {}).keys()) if comp.get("props") else [],
            "file": comp.get("file")
        }
        for name, comp in components.items()
    })


@app.get("/components/{component_name}")
async def get_component(component_name: str):
    """Get detailed information about a specific component."""
    manifest = load_manifest()
    components = manifest.get("components", {})

    if component_name not in components:
        return JSONResponse({
            "error": f"Component '{component_name}' not found",
            "available": list(components.keys())
        }, status_code=404)

    return JSONResponse(components[component_name])


@app.get("/tokens")
async def get_design_tokens():
    """Get all design tokens."""
    manifest = load_manifest()
    return JSONResponse(manifest.get("designTokens", {}))


@app.get("/tokens/{category}")
async def get_token_category(category: str):
    """Get a specific category of design tokens (colors, gradients, typography, etc.)."""
    manifest = load_manifest()
    tokens = manifest.get("designTokens", {})

    if category not in tokens:
        return JSONResponse({
            "error": f"Token category '{category}' not found",
            "available": list(tokens.keys())
        }, status_code=404)

    return JSONResponse(tokens[category])


@app.get("/patterns")
async def get_patterns():
    """Get common code patterns and conventions."""
    manifest = load_manifest()
    return JSONResponse({
        "patterns": manifest.get("patterns", {}),
        "conventions": manifest.get("conventions", {}),
        "utilities": manifest.get("utilities", {})
    })


def main():
    """Run the MCP server."""
    parser = argparse.ArgumentParser(description="Trading Dashboard MCP Server")
    parser.add_argument("--port", type=int, default=8765, help="Port to run server on")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="Host to bind to")
    args = parser.parse_args()

    print(f"""
    ╔═══════════════════════════════════════════════════════════════╗
    ║     Trading Dashboard MCP Server                              ║
    ╠═══════════════════════════════════════════════════════════════╣
    ║  Status: Running                                              ║
    ║  URL: http://{args.host}:{args.port}                              ║
    ║                                                               ║
    ║  Endpoints:                                                   ║
    ║    GET  /           - Health check                            ║
    ║    GET  /mcp        - MCP discovery                           ║
    ║    POST /mcp        - MCP tool calls                          ║
    ║    GET  /manifest   - Full component manifest                 ║
    ║    GET  /components - List all components                     ║
    ║    GET  /tokens     - Design tokens                           ║
    ║    GET  /patterns   - Code patterns & conventions             ║
    ║                                                               ║
    ║  Configure Claude Code:                                       ║
    ║    claude mcp add trading-ui \\                                ║
    ║      --transport http http://localhost:{args.port}/mcp \\         ║
    ║      --scope project                                          ║
    ╚═══════════════════════════════════════════════════════════════╝
    """)

    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
