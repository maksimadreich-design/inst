import { IgApiClient } from 'instagram-private-api';
import { generateDirectReply } from './aiBrain.js';
import { notifyUserNewLead } from './notifier.js';
import dotenv from 'dotenv';
dotenv.config();

const ig = new IgApiClient();

async function login() {
  ig.state.generateDevice(process.env.IG_USERNAME);
  ig.state.appVersion = '319.0.0.38.107';
  ig.state.versionCode = '567990147';
  ig.state.userAgent = 'Instagram 319.0.0.38.107 Android (33/13; 420dpi; 1080x2400; Google/google; Pixel 7; cheetah; cheetah; en_US; 567990147)';
  console.log(`[IG] Авторизація для @${process.env.IG_USERNAME}...`);
  await ig.simulate.preLoginFlow();
  const loggedInUser = await ig.account.login(process.env.IG_USERNAME, process.env.IG_PASSWORD);
  console.log(`[IG] Успішно увійшли як: ${loggedInUser.username} (${loggedInUser.pk})`);
  return loggedInUser;
}

const repliedMessages = new Set();

async function pollDirectMessages() {
  try {
    const inboxFeed = ig.feed.directInbox();
    const threads = await inboxFeed.records();

    for (const thread of threads) {
      const lastItem = thread.items[0];
      if (!lastItem || lastItem.item_type !== 'text') continue;

      // Якщо повідомлення від самого себе - пропускаємо
      if (lastItem.user_id === ig.state.cookieUserId) continue;

      // Якщо вже відповідали на це повідомлення - пропускаємо
      if (repliedMessages.has(lastItem.item_id)) continue;

      repliedMessages.add(lastItem.item_id);

      const clientMessage = lastItem.text;
      const clientUser = thread.users[0]?.username || 'клієнт';
      console.log(`\n📩 Нове повідомлення від @${clientUser}: "${clientMessage}"`);

      // Формуємо історію
      const chatHistory = thread.items
        .slice(0, 6)
        .reverse()
        .map(i => ({
          sender: i.user_id === ig.state.cookieUserId ? 'agent' : 'client',
          text: i.text || ''
        }));

      // Генеруємо відповідь AI
      console.log(`🤖 AI генерує відповідь...`);
      const reply = await generateDirectReply(chatHistory, clientMessage);

      // Відправляємо в Direct
      const threadEntity = ig.entity.directThread(thread.thread_id);
      await threadEntity.broadcastText(reply);
      console.log(`✅ Відповідь надіслана в Direct: "${reply}"`);

      // Сповіщення власнику в Telegram
      await notifyUserNewLead({
        clientUsername: clientUser,
        clientMessage: clientMessage
      });
    }
  } catch (err) {
    console.error('[Помилка опитування Direct]:', err.message);
  }
}

async function main() {
  if (!process.env.IG_USERNAME || !process.env.IG_PASSWORD) {
    console.error('Помилка: Заповни IG_USERNAME та IG_PASSWORD у файлі .env');
    return;
  }

  try {
    await login();
    console.log('🚀 AI-Агент ProstoDev запущений! Слухаємо Direct кожні 15 секунд...');
    
    // Перевірка кожні 15 секунд
    setInterval(pollDirectMessages, 15000);
    pollDirectMessages();
  } catch (error) {
    console.error('Помилка запуску:', error.message);
  }
}

main();
