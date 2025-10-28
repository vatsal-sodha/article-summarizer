import json
import boto3
import requests
from bs4 import BeautifulSoup
from botocore.exceptions import ClientError  # ← ADD THIS IMPORT

bedrock = boto3.client('bedrock-runtime', region_name='us-east-1')

def extract_article_text(url):
    """Fetch and extract main text content from URL"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Remove script and style elements
        for script in soup(["script", "style", "nav", "footer", "header"]):
            script.decompose()
        
        # Get text from common article containers
        article_text = ""
        for tag in ['article', 'main', 'div[class*="content"]', 'div[class*="article"]']:
            article = soup.select_one(tag)
            if article:
                article_text = article.get_text()
                break
        
        if not article_text:
            article_text = soup.get_text()
        
        # Clean up text
        lines = (line.strip() for line in article_text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        text = ' '.join(chunk for chunk in chunks if chunk)
        
        # Limit to first 8000 characters to stay within token limits
        return text[:8000]
    
    except Exception as e:
        raise Exception(f"Failed to fetch article: {str(e)}")

def summarize_with_bedrock(text):
    """Summarize text using Claude via Bedrock"""
    prompt = f"""Please provide a concise summary of the following article. 
    Focus on the main points, key arguments, and important conclusions.
    
    Article text:
    {text}
    
    Summary:"""
    
    body = json.dumps({
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 1000,
        "messages": [
            {
                "role": "user",
                "content": prompt  # ← SIMPLIFIED: Just send string directly
            }
        ]
    })
    
    try:
        print("Calling Bedrock API...")
        response = bedrock.invoke_model(
            modelId='anthropic.claude-3-haiku-20240307-v1:0',
            body=body
        )
        
        response_body = json.loads(response['body'].read())
        print("Response from Bedrock:", json.dumps(response_body))
        
        return response_body['content'][0]['text']
        
    except ClientError as e:
        error_msg = f"Bedrock ClientError: {e.response['Error']['Code']} - {e.response['Error']['Message']}"
        print(error_msg)
        raise Exception(error_msg)  # ← RAISE the error so it's caught by main handler
        
    except Exception as e:
        error_msg = f"Bedrock Error: {str(e)}"
        print(error_msg)
        raise Exception(error_msg)  # ← RAISE the error

def lambda_handler(event, context):
    # Enable CORS
    headers = {
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Headers': 'Content-Type',
        'Access-Control-Allow-Methods': 'POST, OPTIONS',
        'Content-Type': 'application/json'  # ← ADD THIS
    }
    
    # Handle preflight request
    if event.get('httpMethod') == 'OPTIONS':
        return {
            'statusCode': 200,
            'headers': headers,
            'body': ''
        }
    
    try:
        # Parse request body
        body = json.loads(event.get('body', '{}'))
        url = body.get('url')
        print("Received URL:", url)
        
        if not url:
            return {
                'statusCode': 400,
                'headers': headers,
                'body': json.dumps({'error': 'URL is required'})
            }
        
        # Extract article text
        print("Extracting article text...")
        article_text = extract_article_text(url)
        print(f"Extracted {len(article_text)} characters")
        
        # Summarize with Bedrock
        print("Summarizing with Bedrock...")
        summary = summarize_with_bedrock(article_text)
        print(f"Generated summary: {len(summary)} characters")
        
        return {
            'statusCode': 200,
            'headers': headers,
            'body': json.dumps({
                'summary': summary,
                'url': url
            })
        }
    
    except Exception as e:
        print(f"ERROR in lambda_handler: {str(e)}")
        return {
            'statusCode': 500,
            'headers': headers,
            'body': json.dumps({'error': str(e)})
        }
