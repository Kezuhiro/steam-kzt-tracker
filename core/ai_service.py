import json
import logging
from openai import AsyncOpenAI
from core.config import OLLAMA_BASE_URL, OLLAMA_MODEL

logger = logging.getLogger(__name__)

class AIService:
    def __init__(self):
        self.client = AsyncOpenAI(base_url=OLLAMA_BASE_URL, api_key="ollama")
        self.model = OLLAMA_MODEL

    async def think_game_titles(self, user_query: str) -> dict:
        """
        ИИ генерирует английские названия игр и сразу пишет короткое
        экспертное объяснение на русском языке.
        """
        system_prompt = (
            "Ты — харизматичный игровой эксперт. Твоя задача — вспомнить от 2 до 5 игр, "
            "которые ИДЕАЛЬНО подходят под запрос пользователя.\n\n"
            "🔴 ЖЕСТКИЕ ПРАВИЛА ФОРМАТА (НАРУШЕНИЕ ПРИВЕДЕТ К СБОЮ):\n"
            "1. Выдавай ответ СТРОГО в формате: Название на английском | Короткое объяснение на русском.\n"
            "2. Каждая игра должна быть на новой строке.\n"
            "3. Разделитель — строго вертикальная черта '|'.\n"
            "4. Никаких списков, цифр (1., 2.), звездочек, кавычек и приветствий.\n\n"
            "Пример ответа:\n"
            "No Man's Sky | Это бесконечная песочница, где выживание зависит от добычи ресурсов на разных планетах.\n"
            "Starbound | Отличный 2D-выживач с возможностью строить базу и летать по галактике."
        )

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Запрос геймера: {user_query}"}
                ],
                temperature=0.4
            )
            
            content = response.choices[0].message.content.strip()
            
            # Очищаем от случайного Markdown, который ИИ иногда любит добавлять
            content = content.replace("*", "").replace("\"", "")
            
            games_dict = {}
            for line in content.split('\n'):
                if '|' in line:
                    parts = line.split('|', 1)
                    if len(parts) == 2:
                        title = parts[0].strip()
                        reason = parts[1].strip()
                        if title and reason:
                            games_dict[title] = reason
                            
            return games_dict
            
        except Exception as e:
            logger.error(f"Ошибка ИИ-сервиса (think_game_titles): {e}")
            return {}

    async def summarize_reviews(self, game_name: str, reviews: list[str]) -> str:
        # 🔥 Защита видеокарты: берем только первые 15 отзывов для анализа
        safe_reviews = reviews[:15]
        reviews_text = "\n".join([f"- {rev}" for rev in safe_reviews])
        
        system_prompt = (
            f"Ты — игровой эксперт. Сделай краткую выжимку отзывов игроков в Steam на русском языке для игры {game_name}.\n"
            "Структурируй строго по пунктам:\n"
            "🔥 **Главные плюсы:**\n"
            "⚠️ **Главные минусы:**\n"
            "🎮 **Вердикт:**"
        )
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": reviews_text}
                ],
                temperature=0.3
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"Ошибка саммаризации: {e}")
            return "Не удалось обработать отзывы."

ai_service = AIService()