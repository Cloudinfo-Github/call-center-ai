"""
OpenAI Realtime API 整合範例
這是 2025 年架構優化的核心組件
"""

import asyncio
import json
from typing import AsyncGenerator, Dict, Any, List
from openai import AsyncOpenAI
import structlog

logger = structlog.get_logger()


class RealtimeVoiceAgent:
    """
    OpenAI Realtime API 整合

    優勢:
    - 端到端語音處理 (無需分離 STT/TTS)
    - 延遲降低 60-70% (200-300ms vs 500-1000ms)
    - 原生工具調用支援
    - 更自然的對話流程
    """

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4o-realtime-preview",
        voice: str = "alloy",
        instructions: str = "",
        tools: List[Dict[str, Any]] = None
    ):
        self.client = AsyncOpenAI(api_key=api_key)
        self.model = model
        self.voice = voice
        self.instructions = instructions
        self.tools = tools or []

        logger.info(
            "realtime_agent_initialized",
            model=model,
            voice=voice,
            num_tools=len(self.tools)
        )

    async def start_session(
        self,
        audio_stream: AsyncGenerator[bytes, None],
        session_config: Dict[str, Any] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        啟動 Realtime 會話

        Args:
            audio_stream: 輸入音訊流 (16kHz, mono, PCM)
            session_config: 會話配置

        Yields:
            事件字典 (audio, text, function_call等)
        """
        config = {
            "model": self.model,
            "voice": self.voice,
            "instructions": self.instructions,
            "tools": self.tools,
            "modalities": ["audio", "text"],
            "temperature": 0.7,
            **(session_config or {})
        }

        logger.info("starting_realtime_session", config=config)

        try:
            async with self.client.realtime.connect(**config) as session:
                # 建立雙向流
                send_task = asyncio.create_task(
                    self._send_audio(session, audio_stream)
                )
                receive_task = asyncio.create_task(
                    self._receive_events(session)
                )

                # 並行處理發送和接收
                async for event in self._receive_events(session):
                    yield event

        except Exception as e:
            logger.error("realtime_session_error", error=str(e))
            raise
        finally:
            logger.info("realtime_session_ended")

    async def _send_audio(
        self,
        session: Any,
        audio_stream: AsyncGenerator[bytes, None]
    ):
        """發送音訊到 Realtime API"""
        try:
            async for audio_chunk in audio_stream:
                await session.send_audio(audio_chunk)
                logger.debug(
                    "audio_sent",
                    chunk_size=len(audio_chunk)
                )
        except Exception as e:
            logger.error("audio_send_error", error=str(e))

    async def _receive_events(
        self,
        session: Any
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """接收來自 Realtime API 的事件"""
        try:
            async for event in session.events():
                event_type = event.get("type")

                logger.debug("event_received", type=event_type)

                # 音訊回應
                if event_type == "response.audio.delta":
                    yield {
                        "type": "audio",
                        "data": event.get("delta"),
                        "timestamp": event.get("timestamp")
                    }

                # 文字回應
                elif event_type == "response.text.delta":
                    yield {
                        "type": "text",
                        "data": event.get("delta"),
                        "timestamp": event.get("timestamp")
                    }

                # 工具調用
                elif event_type == "response.function_call":
                    function_name = event.get("name")
                    arguments = json.loads(event.get("arguments", "{}"))

                    logger.info(
                        "function_call_received",
                        function=function_name,
                        arguments=arguments
                    )

                    # 執行工具
                    result = await self._execute_tool(
                        function_name,
                        arguments
                    )

                    # 回傳結果給 API
                    await session.send_function_result(
                        call_id=event.get("call_id"),
                        result=result
                    )

                    yield {
                        "type": "function_call",
                        "name": function_name,
                        "arguments": arguments,
                        "result": result
                    }

                # 中斷檢測
                elif event_type == "input_audio_buffer.speech_started":
                    logger.info("user_interrupted")
                    yield {
                        "type": "interruption",
                        "timestamp": event.get("timestamp")
                    }

                # 錯誤處理
                elif event_type == "error":
                    logger.error(
                        "realtime_api_error",
                        error=event.get("error")
                    )
                    yield {
                        "type": "error",
                        "error": event.get("error")
                    }

        except Exception as e:
            logger.error("event_receive_error", error=str(e))

    async def _execute_tool(
        self,
        function_name: str,
        arguments: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        執行工具調用

        這裡應該連接到現有的工具系統
        (app/helpers/llm_tools.py 中的 DefaultPlugin)
        """
        logger.info(
            "executing_tool",
            function=function_name,
            arguments=arguments
        )

        # TODO: 整合現有工具系統
        # from app.helpers.llm_tools import DefaultPlugin
        # plugin = DefaultPlugin(...)
        # return await getattr(plugin, function_name)(**arguments)

        # 暫時返回模擬結果
        return {
            "success": True,
            "function": function_name,
            "result": f"已執行 {function_name}"
        }


class RealtimeCallHandler:
    """
    完整的通話處理器
    整合 Realtime API 與現有系統
    """

    def __init__(
        self,
        openai_api_key: str,
        system_prompt: str,
        tools: List[Dict[str, Any]]
    ):
        self.agent = RealtimeVoiceAgent(
            api_key=openai_api_key,
            instructions=system_prompt,
            tools=tools
        )

    async def handle_call(
        self,
        call_id: str,
        audio_input: AsyncGenerator[bytes, None],
        audio_output_callback: callable
    ):
        """
        處理完整通話流程

        Args:
            call_id: 通話 ID
            audio_input: 輸入音訊流
            audio_output_callback: 輸出音訊回調
        """
        logger.info("handling_call", call_id=call_id)

        # 啟動 Realtime 會話
        async for event in self.agent.start_session(audio_input):
            event_type = event.get("type")

            # 處理音訊輸出
            if event_type == "audio":
                await audio_output_callback(event["data"])

            # 處理文字 (用於日誌和分析)
            elif event_type == "text":
                logger.info(
                    "assistant_text",
                    call_id=call_id,
                    text=event["data"]
                )

            # 處理工具調用
            elif event_type == "function_call":
                logger.info(
                    "function_executed",
                    call_id=call_id,
                    function=event["name"],
                    result=event["result"]
                )

            # 處理中斷
            elif event_type == "interruption":
                logger.info(
                    "user_interruption",
                    call_id=call_id
                )

            # 處理錯誤
            elif event_type == "error":
                logger.error(
                    "call_error",
                    call_id=call_id,
                    error=event["error"]
                )


# 使用範例
async def example_usage():
    """範例：如何使用 Realtime API"""

    # 1. 定義系統提示
    system_prompt = """
    你是 Contoso 保險公司的 AI 客服代表 Amélie。
    你的職責是協助客戶處理保險理賠。

    重要指示：
    - 保持友善和專業
    - 簡潔回答 (1-2 句，除非被要求詳細說明)
    - 使用繁體中文溝通
    - 收集必要的理賠資訊
    """

    # 2. 定義可用工具
    tools = [
        {
            "type": "function",
            "name": "create_claim",
            "description": "建立新的保險理賠",
            "parameters": {
                "type": "object",
                "properties": {
                    "caller_name": {
                        "type": "string",
                        "description": "客戶姓名"
                    },
                    "incident_date": {
                        "type": "string",
                        "description": "事故日期 (ISO 8601)"
                    },
                    "description": {
                        "type": "string",
                        "description": "事故描述"
                    }
                },
                "required": ["caller_name", "incident_date", "description"]
            }
        },
        {
            "type": "function",
            "name": "transfer_to_agent",
            "description": "轉接到人工客服",
            "parameters": {
                "type": "object",
                "properties": {
                    "reason": {
                        "type": "string",
                        "description": "轉接原因"
                    }
                },
                "required": ["reason"]
            }
        },
        {
            "type": "function",
            "name": "end_call",
            "description": "結束通話",
            "parameters": {
                "type": "object",
                "properties": {
                    "summary": {
                        "type": "string",
                        "description": "通話摘要"
                    }
                }
            }
        }
    ]

    # 3. 創建處理器
    handler = RealtimeCallHandler(
        openai_api_key="your-api-key",
        system_prompt=system_prompt,
        tools=tools
    )

    # 4. 模擬音訊流
    async def mock_audio_input():
        """模擬音訊輸入"""
        # 實際應用中，這會是來自 Azure Communication Services 的音訊
        for _ in range(10):
            yield b'\x00' * 1024  # 模擬音訊數據
            await asyncio.sleep(0.1)

    # 5. 音訊輸出回調
    async def audio_output_callback(audio_data: bytes):
        """處理輸出音訊"""
        # 實際應用中，這會發送到 Azure Communication Services
        print(f"輸出音訊: {len(audio_data)} bytes")

    # 6. 處理通話
    await handler.handle_call(
        call_id="test-call-123",
        audio_input=mock_audio_input(),
        audio_output_callback=audio_output_callback
    )


if __name__ == "__main__":
    # 執行範例
    asyncio.run(example_usage())
