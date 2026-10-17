import TelegramBot from 'node-telegram-bot-api';
import dotenv from 'dotenv';
dotenv.config();

let bot = null;

if (process.env.TELEGRAM_BOT_TOKEN) {
  bot = new TelegramBot(process.env.TELEGRAM_BOT_TOKEN, { polling: false });
}

export async function notifyUserNewLead({ clientUsername, clientPhone, clientMessage, appointmentTime }) {
  if (!bot || !process.env.TELEGRAM_MY_CHAT_ID) {
    console.log('[Telegram Notification Skipped]: Не заданий токен або Chat ID');
    return;
  }

  const message = `
🔥 *НОВИЙ ЛІД З INSTAGRAM (@${clientUsername || 'клієнт'})*!

📩 *Останнє повідомлення:*
"${clientMessage}"

${clientPhone ? `📱 *Телефон / контакт:* ${clientPhone}\n` : ''}
${appointmentTime ? `📅 *Запит на зустріч:* ${appointmentTime}\n` : ''}
🚀 *Агент відповів у Direct і очікує підтвердження.*
`;

  try {
    await bot.sendMessage(process.env.TELEGRAM_MY_CHAT_ID, message, { parse_mode: 'Markdown' });
    console.log(`[Telegram] Сповіщення успішно надіслано власнику!`);
  } catch (err) {
    console.error(`[Telegram Error]:`, err.message);
  }
}
