import datetime
import json

from django.conf import settings
from django.core.mail import EmailMessage
from openai import AsyncOpenAI
from phonenumber_field.phonenumber import PhoneNumber
from twilio.rest import Client

from .prompt import PROMPT
from .rag import run_rag_pipeline


class LlmClient:
    def __init__(self):
        # we use openrouter for easy access and interchangability with other AI models
        self.client = AsyncOpenAI(
            base_url="https://openrouter.ai/api/v1", api_key=settings.OPENROUTER_API_KEY
        )
        self.begin_sentence = """Hi there! My name is Amy, and I'm a your AI assistant. I'm here to help you with any questions you might have about your documents. How can I assist you today?"""
        self.agent_prompt = PROMPT

    def prepare_functions(self):
        # example function
        functions = [
            {
                "type": "function",
                "function": {
                    "name": "send_instruction_video",
                    "description": "Sends the user a video link with instructions on how to use a medication via email or SMS.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "method": {
                                "type": "string",
                                "enum": ["email", "sms"],
                                "description": "The method to send the video link (email or sms).",
                            },
                            "contact_info": {
                                "type": "string",
                                "description": "The email or phone number to send the video link to. The phone number should be in E.164 format.",
                            },
                        },
                        "required": ["method", "contact_info"],
                    },
                },
            }
        ]
        return functions

    def draft_begin_message(self):
        return {
            "response_id": 0,
            "content": self.begin_sentence,
            "content_complete": True,
            "first_message": True,
            "role": "assistant",
        }

    async def draft_response(self, request):
        func_call = {}
        func_arguments = ""
        request_with_context = await self.get_context(request)
        stream = await self.client.chat.completions.create(
            model="google/gemini-pro-1.5",
            messages=request_with_context["messages"],
            stream=True,
            # tools=self.prepare_functions(),
        )
        first_message = True
        async for chunk in stream:
            if chunk.choices[0].delta.tool_calls:
                tool_calls = chunk.choices[0].delta.tool_calls[0]
                if tool_calls.id:
                    if func_call:
                        # Another function received, old function complete, can break here.
                        break
                    func_call = {
                        "id": tool_calls.id,
                        "func_name": tool_calls.function.name or "",
                        "arguments": {},
                    }
                else:
                    # append argument
                    func_arguments += tool_calls.function.arguments or ""

            if chunk.choices[0].delta.content:
                yield {
                    "response_id": int(request_with_context["response_id"]) + 1,
                    "content": chunk.choices[0].delta.content,
                    "content_complete": False,
                    "first_message": first_message,
                    "role": "assistant",
                }
                first_message = False

        if func_call:
            if func_call["func_name"] == "send_instruction_video":
                func_call["arguments"] = json.loads(func_arguments)
                method = func_call["arguments"]["method"]
                contact_info = func_call["arguments"]["contact_info"]
                result = await self.send_video(method, contact_info)
                if not result:
                    content = "I'm sorry but I was unable to send the video link. Please try again later."
                if func_call["arguments"]["method"] == "email":
                    content = f"I have sent you an email with a video link that will show you how to inject the medicine. Please check your email. Here is the link: <a href='# target='_blank'>dummy link</a>"
                else:
                    content = "I have sent you an SMS with a video link that will show you how to inject the medicine. Please check your phone. Here is the link: dummy link"

                yield {
                    "response_id": int(request_with_context["response_id"]) + 1,
                    "content": content,
                    "content_complete": True,
                    "first_message": first_message,
                    "role": "assistant",
                }
            # Add more functions here
        else:
            yield {
                "response_id": int(request_with_context["response_id"]) + 1,
                "content": "",
                "content_complete": True,
                "first_message": first_message,
                "role": "assistant",
            }

    async def send_video(self, method, contact_info):
        if method == "email" and "@" in contact_info:
            to = contact_info
            # change to html emal
            email = EmailMessage(
                "Instruction Video",
                "Here is the video link: <a href='#' target='_blank'>dummy link</a>",
                settings.DEFAULT_EMAIL_FROM,
                [to],
            )
            email.content_subtype = "html"
            email.send()

        elif method == "sms":
            account_sid = settings.TWILIO_ACCOUNT_SID
            api_key_sid = settings.TWILIO_API_KEY
            api_key_secret = settings.TWILIO_API_SECRET
            to = PhoneNumber.from_string(contact_info).as_e164

            # Initialize the Twilio client with the API key
            client = Client(api_key_sid, api_key_secret, account_sid)
            message = client.messages.create(
                body="Here is the video link: dummy link",
                from_="+11234321123",
                to=to,
            )

        return True

    async def get_context(self, request):
        """if the last message was from the user, we can append a context/background info to the message
        that came from a RAG pipelines
        """
        messages = request["messages"]
        last_message = messages[-1]
        context = None
        if last_message["role"] == "user":
            context = await run_rag_pipeline(messages)

        # if you don't have a rag pipeline, it will always be None, so this function will always return the request as is
        if context:
            last_message["content"] = (
                f"{last_message['content']}\n Background information: {context}"
            )
            # pop the last message and append the new message
            messages.pop()
            messages.append(last_message)
            request["messages"] = messages

        return request
