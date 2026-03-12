/**
 * Точка входа webhook Telegram. doPost принимает update и передаёт в processUpdate.
 * Веб-приложение обязано возвращать TextOutput — иначе «Сбой выполнения».
 * Дедупликация по update_id защищает от повторов при retry Telegram.
 */
function doPost(e) {
  var ok = ContentService.createTextOutput('OK').setMimeType(ContentService.MimeType.TEXT);
  try {
    if (!e || !e.postData || !e.postData.contents) {
      return ok;
    }
    var update = JSON.parse(e.postData.contents);
    var uid = update.update_id;
    if (uid != null && isUpdateAlreadyProcessed(uid)) {
      return ok;
    }
    var chatId = update.message ? update.message.chat.id : (update.callback_query ? update.callback_query.message.chat.id : null);
    var text = update.message ? (update.message.text || '[media]') : (update.callback_query ? 'cb:' + update.callback_query.data : '');
    logInfo('doPost: chatId=' + chatId + ' ' + text);
    processUpdate(update);
    if (uid != null) markUpdateProcessed(uid);
    return ok;
  } catch (err) {
    logErrorWithException('doPost', err);
    return ok;
  }
}

var CACHE_UPDATE_PREFIX = 'tg_up_';
var CACHE_UPDATE_TTL = 120;

function isUpdateAlreadyProcessed(updateId) {
  try {
    var v = CacheService.getScriptCache().get(CACHE_UPDATE_PREFIX + updateId);
    return v === '1';
  } catch (e) {
    return false;
  }
}

function markUpdateProcessed(updateId) {
  try {
    CacheService.getScriptCache().put(CACHE_UPDATE_PREFIX + updateId, '1', CACHE_UPDATE_TTL);
  } catch (e) {}
}

function doGet(e) {
  return ContentService.createTextOutput('OK').setMimeType(ContentService.MimeType.TEXT);
}

/**
 * Установить webhook Telegram.
 * В webhookUrl подставьте ТОЛЬКО URL из Развёртывание → Управление развёртываниями (кнопка копирования).
 * Правильный формат: https://script.google.com/macros/s/XXXX/exec
 * НЕ копируйте URL из адресной строки редактора (/edit) и без фрагментов (#...).
 */
function setTelegramWebhook() {
  var token = getBotToken();
  if (!token) {
    Logger.log('BOT_TOKEN не задан в свойствах скрипта или Config');
    return;
  }
  var webhookUrl = 'ВСТАВЬТЕ_СЮДА_ВАШ_URL_РАЗВЁРТЫВАНИЯ';
  if (webhookUrl.indexOf('/edit') !== -1 || webhookUrl.indexOf('#') !== -1) {
    Logger.log('ОШИБКА: Недопустимый URL. Скопируйте URL из Развёртывание → Управление развёртываниями (не из адресной строки редактора). Формат: https://script.google.com/macros/s/.../exec');
    return;
  }
  if (webhookUrl.indexOf('/exec') === -1) {
    Logger.log('Предупреждение: URL должен заканчиваться на /exec (не /dev).');
  }
  var url = 'https://api.telegram.org/bot' + token + '/setWebhook?url=' + encodeURIComponent(webhookUrl);
  var response = UrlFetchApp.fetch(url);
  Logger.log(response.getContentText());
}

/**
 * Удалить webhook (если установлен неверный URL). После этого вызовите setTelegramWebhook с правильным URL.
 */
function deleteTelegramWebhook() {
  var token = getBotToken();
  if (!token) {
    Logger.log('BOT_TOKEN не задан');
    return;
  }
  var response = UrlFetchApp.fetch('https://api.telegram.org/bot' + token + '/deleteWebhook');
  Logger.log(response.getContentText());
}

/**
 * Проверить текущий webhook в Telegram. Запустите вручную — в логах увидите URL или «не установлен».
 */
function checkWebhookInfo() {
  var token = getBotToken();
  if (!token) {
    Logger.log('BOT_TOKEN не задан');
    return;
  }
  var response = UrlFetchApp.fetch('https://api.telegram.org/bot' + token + '/getWebhookInfo');
  var data = JSON.parse(response.getContentText());
  if (data.ok && data.result) {
    var wh = data.result.url || '(не установлен)';
    Logger.log('Текущий webhook: ' + wh);
  } else {
    Logger.log(JSON.stringify(data));
  }
}

/**
 * Polling: опрос getUpdates каждую минуту. Запускается триггером triggerPollTelegram.
 * Вызовите switchToPolling() один раз — webhook удалится, добавится триггер.
 */
var PROP_POLLING_OFFSET = 'POLLING_OFFSET';

function triggerPollTelegram() {
  try {
    pollTelegramUpdates();
  } catch (e) {
    logErrorWithException('triggerPollTelegram', e);
  }
}

function pollTelegramUpdates() {
  var token = getBotToken();
  if (!token) return;
  var props = PropertiesService.getScriptProperties();
  var offset = parseInt(props.getProperty(PROP_POLLING_OFFSET) || '0', 10);
  var url = 'https://api.telegram.org/bot' + token + '/getUpdates?offset=' + offset + '&timeout=30';
  var response;
  try {
    response = UrlFetchApp.fetch(url, { muteHttpExceptions: true });
  } catch (e) {
    logErrorWithException('pollTelegramUpdates fetch', e);
    return;
  }
  var data;
  try {
    data = JSON.parse(response.getContentText());
  } catch (e) {
    return;
  }
  if (!data.ok || !data.result || data.result.length === 0) {
    return;
  }
  var lastId = offset;
  for (var i = 0; i < data.result.length; i++) {
    var update = data.result[i];
    lastId = update.update_id;
    try {
      var chatId = update.message ? update.message.chat.id : (update.callback_query ? update.callback_query.message.chat.id : null);
      var text = update.message ? (update.message.text || '[media]') : (update.callback_query ? 'cb:' + update.callback_query.data : '');
      logInfo('poll: chatId=' + chatId + ' ' + text);
      processUpdate(update);
    } catch (e) {
      logErrorWithException('poll processUpdate', e);
    }
  }
  props.setProperty(PROP_POLLING_OFFSET, String(lastId + 1));
}

/**
 * Переключиться на polling: удалить webhook, добавить триггер опроса каждую минуту.
 */
function switchToPolling() {
  deleteTelegramWebhook();
  if (typeof deleteAllTriggers === 'function') deleteAllTriggers();
  var ss = getSpreadsheet();
  if (!ss) {
    Logger.log('Скрипт должен быть привязан к таблице');
    return;
  }
  ScriptApp.newTrigger('triggerPollTelegram')
    .timeBased()
    .everyMinutes(1)
    .create();
  ScriptApp.newTrigger('triggerMainWork18').timeBased().everyDays(1).atHour(18).create();
  ScriptApp.newTrigger('triggerSecondJob00').timeBased().everyDays(1).atHour(0).nearMinute(5).create();
  ScriptApp.newTrigger('triggerPayday10').timeBased().everyDays(1).atHour(10).create();
  ScriptApp.newTrigger('triggerReminderMain19').timeBased().everyDays(1).atHour(19).create();
  ScriptApp.newTrigger('triggerReminderSecond00').timeBased().everyDays(1).atHour(0).nearMinute(30).create();
  ScriptApp.newTrigger('triggerProdCalendar1st').timeBased().onMonthDay(1).atHour(1).create();
  Logger.log('Polling включён. Webhook удалён. Триггер опроса — каждую минуту.');
}

/**
 * Вернуться на webhook. Удаляет триггер polling. Затем вызовите setTelegramWebhook() с URL.
 */
function switchToWebhook() {
  if (typeof deleteAllTriggers === 'function') deleteAllTriggers();
  if (typeof installTriggers === 'function') installTriggers();
  Logger.log('Триггеры переустановлены (без polling). Вызовите setTelegramWebhook() с URL развёртывания.');
}

/**
 * Показать URL текущего скрипта. Обычно возвращает /dev — он НЕ подходит для webhook.
 * Для webhook: Развёртывание → Управление развёртываниями → кнопка копирования у "Веб-приложение" → URL с /exec.
 */
function getMyWebAppUrl() {
  try {
    var url = ScriptApp.getService().getUrl();
    Logger.log('URL (часто /dev): ' + url);
    if (url.indexOf('/dev') !== -1) {
      Logger.log('');
      Logger.log('ЭТОТ URL НЕ ПОДХОДИТ для webhook!');
      Logger.log('Скопируйте URL из: Развёртывание → Управление развёртываниями');
      Logger.log('Нажмите кнопку копирования у развёртывания "Веб-приложение". URL должен заканчиваться на /exec.');
    }
  } catch (e) {
    Logger.log('Скопируйте URL из Развёртывание → Управление развёртываниями.');
  }
}
