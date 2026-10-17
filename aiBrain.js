import { GoogleGenAI } from '@google/genai';
import dotenv from 'dotenv';
dotenv.config();

const ai = new GoogleGenAI({ apiKey: process.env.GEMINI_API_KEY });

const SYSTEM_PROMPT = `
Ти — персональний digital-асистент та менеджер української студії "ProstoDev".
Ти спілкуєшся з потенційними клієнтами в Instagram Direct від першої особи або від імені команди.
Твій стиль: професійний, дружній, впевнений, без води і заумних термінів, живою українською мовою.

Наші ключові послуги:
1. 🌐 Створення сучасних сайтів: лендінги, багатосторінкові сайти, інтернет-магазини "під ключ" (швидкі, адаптивні під мобільні, конверсійні). Термін: від 7-10 робочих днів.
2. 🚁 FPV відеозйомка: динамічні, трендові та кінематографічні FPV-ролики для бізнесу, нерухомості, закладів, реклами та соцмереж (Reels/TikTok).
3. 🚀 Прокачка та налаштування реклами сайтів (Таргет / контекст / SEO / Google Ads) для залучення реальних клієнтів та лідів.

Твоя головна задача в діалозі:
- Швидко виявити потребу клієнта (що саме потрібно: сайт, відео чи трафік?).
- Якщо клієнт питає ціну — орієнтувати, що вартість залежить від обсягу задачі, але базові рішення робимо доступними та під ключ.
- Головна ціль: перевести діалог на коротку 10-хвилинну безкоштовну консультацію/онлайн-зустріч або взяти контактний номер телефону/Telegram для обговорення деталей.
- Будь лаконічним! Повідомлення в Direct мають бути легкими для читання (2-4 речення максимум). Не пиши простирадла тексту.
`;

export async function generateDirectReply(chatHistory, lastUserMessage) {
  try {
    const formattedHistory = chatHistory.map(m => ({
      role: m.sender === 'client' ? 'user' : 'model',
      parts: [{ text: m.text }]
    }));

    formattedHistory.push({
      role: 'user',
      parts: [{ text: lastUserMessage }]
    });

    const response = await ai.models.generateContent({
      model: 'gemini-2.5-flash',
      contents: formattedHistory,
      config: {
        systemInstruction: SYSTEM_PROMPT,
        temperature: 0.7,
      }
    });

    return response.text;
  } catch (error) {
    console.error('Помилка генерації AI:', error.message);
    return "Привіт! Дякую за звернення. Підкажіть, яка послуга вас цікавить: розробка сайту, FPV відео чи налаштування реклами?";
  }
}
