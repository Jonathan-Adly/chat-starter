from django.conf import settings
from openai import OpenAI

from colivara_py import Colivara

def run_rag_pipeline(messages):
    rag_client = Colivara(
        base_url="http://localhost:8001", api_key="m1TdGK5HeNRZjMbgClus0xCBsMuiyr8o"
      )
    # first step - as this multi-conversation turns is to transform the messages in a RAG-appropriate query
    # example: message = ["role": "user", "content": "What is the capital of Brazil?", "assistant": "Brazil", "user": "how about france?"]
    # query should be = What the capital of France?
    prompt = """ 
    You are given a conversation between a user and an assistant. We need to transform the last message from the user into a question appropriate for a RAG pipeline.
    Given the nature and flow of conversation. 

    Example #1:
    User: What is the capital of Brazil?
    Assistant: Brazil
    User: How about France?
    RAG Query: What is the capital of France?
    <reasoning> 
    Somewhat related query, however, if we simply use "how about france?" without any transformation, the RAG pipeline will not be able to provide a meaningful response.
    The transformation took the previous question (what the capital of Brazil?) as a strong hint about the user intention
    </reasoning>

    Example #2:
    User: What is the policy on working from home? 
    Assistant: <policy details>
    User: What is the side effects of Wegovy?
    RAG Query: What are the side effects of Wegovy?
    <reasoning>
    The user is asking for the side effects of Wegovy, the transformation is straightforward, we just need to slightly adjust. 
    The previous question was about a completely different topic, so it has no influence on the transformation.
    </reasoning>

    Example #3:
    User: What is the highest monetary value of a gift I can recieve from a client?
    Assistant: <policy details>
    User: Is there a time limit between gifts?
    RAG Query: What is the highest monetary value of a gift I can recieve from a client within a specific time frame?
    <reasoning>
    The user queries are very related and a continuation of the same question. He is asking for more details about the same topic.
    The transformation needs to take into account the previous question and the current one.
    </reasoning>

    Example #4:
    User: Hello!
    RAQ Query: Not applicable
    <reasoning>
    The user is simply greeting the assistant, there is no question to transform. This applies to any non-question message,
    </reasoning>

    Coversation:
    """
    for message in messages:
        prompt += f"{message['role']}: {message['content']}\n"

    client = OpenAI(
        base_url="https://openrouter.ai/api/v1", api_key=settings.OPENROUTER_API_KEY
    )

    response = client.chat.completions.create(
        model="openai/gpt-4o-2024-08-06",
        messages=[{"role": "assistant", "content": prompt}],
        stream=False,
    )
    query = response.choices[0].message.content
    # take out RAG Query: from the response
    if "not applicable" in query.lower():
        return []
    if "rag query:" in query.lower():
        query = query.split("ry:")[1].strip()
        # remove any reasonings tags
        query = query.split("<reasoning>")[0].strip()
    print(f"This what we will send to the RAG pipeline: {query}")
    results = rag_client.search(query=query, collection_name="mount sinai")
    results = results.results
    # example result: 
    """{
  "query": "string",
  "results": [
    {
      "collection_name": "string",
      "collection_id": 0,
      "collection_metadata": {},
      "document_name": "string",
      "document_id": 0,
      "document_metadata": {},
      "page_number": 0,
      "raw_score": 0,
      "normalized_score": 0,
      "img_base64": "string"
    }
    ]
    }"""

    context= []
    for result in results:
        document_title = result.document_name
        page_num = result.page_number
        base64 = result.img_base64
        # base64 doesn;t have data: part so we need to add it
        if "data:image" not in base64:
            base64 = f"data:image/png;base64,{base64}"
        context.append(
            {
                "metadata": f"{document_title} - Page {page_num}",
                "base64": base64,
            }
        )
    return context
    