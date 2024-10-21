import asyncio
import json
from urllib.parse import parse_qs

from channels.generic.websocket import AsyncWebsocketConsumer

from .llm import LlmClient


class LLMWebsocketChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.chat_id = self.scope["url_route"]["kwargs"]["chat_id"]
        # url comes with parameters for classes as such /ws/llm/chat/<chat_id>/?dynamic-classes=%7B%22assistant_outdiv%22%3A%22flex%20items-start
        # Extract the raw query string
        query_string = self.scope["query_string"].decode()

        # Parse the query string into a dictionary
        query_params = parse_qs(query_string)

        # Extract the dynamic-classes parameter, if it exists
        dynamic_classes_encoded = query_params.get("dynamic-classes", [None])[0]

        self.dynamic_classes = (
            json.loads(dynamic_classes_encoded) if dynamic_classes_encoded else {}
        )
        await self.accept()
        print(f"Handle llm ws for: {self.chat_id}")

        self.llm_client = LlmClient()
        self.response_id = 0
        self.messages = [
            {
                "role": "system",
                "content": self.llm_client.agent_prompt,
            }
        ]

        first_event = self.llm_client.draft_begin_message()
        self.messages.append(
            {
                "content": first_event["content"],
                "role": "assistant",
            }
        )
        htmx_data = await self.format_to_htmx(first_event)
        await self.send(text_data=htmx_data)

    # This method is called when the connection is closed
    async def disconnect(self, close_code):
        print(f"Closing llm ws for: {self.chat_id}")

    # This method is called when a message is received via a chat msg
    async def receive(self, text_data):
        try:
            # Process the received message here
            request = json.loads(text_data)
            # we start at 0. This is the response_id of the first message that the server sends
            # the client first sends a message with response_id = 1. This what the user sends (self.response_id = 1)
            # the stream_response, increments the response_id by 1 --> gets to htmx --> updated the response_id on the client --> client has response_id = 2
            # the client sends a message with response_id = 2. This is what the user sends (self.response_id = 2)
            self.response_id = int(request["response_id"])
            self.messages.append(
                {
                    "content": request["content"],
                    "role": "user",
                }
            )
            request["messages"] = self.messages
            request["first_message"] = True
            request["content_complete"] = True
            request["role"] = "user"
            htmx_data = await self.format_to_htmx(request)
            await self.send(text_data=htmx_data)
            asyncio.create_task(self.stream_response(request))
        except Exception as e:
            print(f"LLM WebSocket error for {self.chat_id}: {e}")

    # This method is called to AI responses to the client
    async def stream_response(self, request):
        chunks = []
        async for event in self.llm_client.draft_response(request):
            htmx_data = await self.format_to_htmx(event)
            await self.send(text_data=htmx_data)
            chunks.append(event["content"])
        self.messages.append({"role": "system", "content": "".join(chunks)})

    async def format_to_htmx(self, text_data_json):
        content = text_data_json["content"]
        # this comes from the client. It should be the response_id of the last message sent by the client
        response_id = int(text_data_json["response_id"])
        first_message = text_data_json["first_message"]
        content_complete = text_data_json["content_complete"]
        role = text_data_json["role"].title()
        image = text_data_json.get("image", None)
        if role == "Assistant":
            outer_div = self.dynamic_classes.get("assistant_outdiv", "")
            inner_div = self.dynamic_classes.get("assistant_innerdiv", "")
            p_style = self.dynamic_classes.get("assistant_p_style", "")
                
        else:
            outer_div = self.dynamic_classes.get("user_outdiv", "")
            inner_div = self.dynamic_classes.get("user_innerdiv", "")
            p_style = self.dynamic_classes.get("user_p_style", "")
        
        image_container_style = self.dynamic_classes.get("image_container_style", "")
        image_style = self.dynamic_classes.get("image_style", "")
        image_caption = self.dynamic_classes.get("image_caption", "")
        # in the case of the first message, we add a new div to the message log
        if first_message:
            # previous div was chat-0, so we increment by 1
            chat_id = f"chat-{response_id + 1}"
            template = f"""<div id="messageLog" hx-swap-oob="beforeend">
              <div class="{outer_div}">
                <div class="{inner_div}">
                    <div>
                        <p class="font-semibold text-gray-800 mb-2">{role}</p>
                       <div id="{chat_id}"class="{p_style}">{content}</div>
                    </div>
                </div>
            </div>
                """
        else:
             # not a first message, so we append content to the <p> tag with the id chat-{response_id}
            chat_id = f"chat-{response_id + 1}"
            if image:
                template = f"""
                <div id={chat_id} hx-swap-oob="beforeend">
                         <div class="{image_container_style}">
                            <img
                                alt="Uploaded document"
                                src="{image}"
                                class="{image_style}"
                            />
                            <p class="{image_caption}">{content}</p>
                        </div>
                </div>
                """
            
            else:
                template = f"""<div id={chat_id} hx-swap-oob="beforeend">{content}</div>"""

        if content_complete and not image:
            response_id += 1
            template = (
                template
                + f"""<input type="hidden" name="response_id" value={response_id} id="response_id">"""
            )

        return template
