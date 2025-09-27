"""
kb_lookup Tool
Retrieves Well-Architected Framework guidance and evidence from Knowledge Base
"""

import json
import logging
import os
from typing import Dict, Any, List

import boto3

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize AWS clients
bedrock_agent_runtime = boto3.client('bedrock-agent-runtime')

# Environment variables
KNOWLEDGE_BASE_ID = os.environ.get('KNOWLEDGE_BASE_ID')


def search_knowledge_base(topic: str, pillar: str = None) -> List[Dict[str, Any]]:
    """Search Bedrock Knowledge Base for relevant guidance"""
    try:
        # Construct query
        query = topic
        if pillar:
            query = f"{topic} {pillar} Well-Architected Framework"
        
        # Search knowledge base
        response = bedrock_agent_runtime.retrieve(
            knowledgeBaseId=KNOWLEDGE_BASE_ID,
            retrievalQuery={
                'text': query
            },
            retrievalConfiguration={
                'vectorSearchConfiguration': {
                    'numberOfResults': 3
                }
            }
        )
        
        results = []
        for result in response.get('retrievalResults', []):
            results.append({
                'content': result.get('content', {}).get('text', ''),
                'location': result.get('location', {}),
                'score': result.get('score', 0.0),
                'source_uri': result.get('location', {}).get('s3Location', {}).get('uri', '')
            })
        
        return results
    
    except Exception as e:
        logger.error(f"Error searching knowledge base: {e}")
        return []


def format_evidence_snippet(result: Dict[str, Any]) -> str:
    """Format a single evidence snippet"""
    content = result.get('content', '')
    source_uri = result.get('source_uri', '')
    
    # Truncate content to 1-2 sentences
    sentences = content.split('. ')
    if len(sentences) > 2:
        content = '. '.join(sentences[:2]) + '.'
    
    snippet = content
    if source_uri:
        snippet += f" [Source]({source_uri})"
    
    return snippet


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    kb_lookup tool handler
    
    Input:
    {
        "topic": "S3 encryption at rest requirement",
        "pillar": "Security"
    }
    
    Output:
    {
        "status": "success|error",
        "data": {
            "snippet": "Enable SSE-KMS for S3 buckets...",
            "source_url": "...",
            "evidence": [
                {
                    "content": "...",
                    "source_uri": "...",
                    "score": 0.95
                }
            ]
        },
        "error": "error message if status is error"
    }
    """
    try:
        # Validate input
        if 'topic' not in event:
            return {
                'status': 'error',
                'error': 'Missing required parameter: topic'
            }
        
        topic = event['topic']
        pillar = event.get('pillar')
        
        # Search knowledge base
        results = search_knowledge_base(topic, pillar)
        
        if not results:
            return {
                'status': 'success',
                'data': {
                    'snippet': f"No specific guidance found for: {topic}",
                    'source_url': None,
                    'evidence': []
                }
            }
        
        # Get best result
        best_result = max(results, key=lambda x: x.get('score', 0))
        
        # Format evidence snippet
        snippet = format_evidence_snippet(best_result)
        
        result = {
            'snippet': snippet,
            'source_url': best_result.get('source_uri'),
            'evidence': results
        }
        
        logger.info(f"Found {len(results)} knowledge base results for: {topic}")
        
        return {
            'status': 'success',
            'data': result
        }
    
    except Exception as e:
        logger.error(f"Error in kb_lookup: {e}")
        return {
            'status': 'error',
            'error': str(e)
        }
