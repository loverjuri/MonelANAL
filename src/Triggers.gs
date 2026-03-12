/**
 * Time-driven триггеры (Europe/Moscow).
 * GAS: время в триггерах задаётся в часовом поясе скрипта (appsscript.json: timeZone: Europe/Moscow).
 */
function installTriggers() {
  deleteAllTriggers();
  var ss = getSpreadsheet();
  if (!ss) return;

  ScriptApp.newTrigger('triggerMainWork18')
    .timeBased()
    .everyDays(1)
    .atHour(18)
    .create();

  ScriptApp.newTrigger('triggerSecondJob00')
    .timeBased()
    .everyDays(1)
    .atHour(0)
    .nearMinute(5)
    .create();

  ScriptApp.newTrigger('triggerPayday10')
    .timeBased()
    .everyDays(1)
    .atHour(10)
    .create();

  ScriptApp.newTrigger('triggerReminderMain19')
    .timeBased()
    .everyDays(1)
    .atHour(19)
    .create();

  ScriptApp.newTrigger('triggerReminderSecond00')
    .timeBased()
    .everyDays(1)
    .atHour(0)
    .nearMinute(30)
    .create();

  ScriptApp.newTrigger('triggerProdCalendar1st')
    .timeBased()
    .onMonthDay(1)
    .atHour(1)
    .create();

  Logger.log('Triggers installed.');
}

function deleteAllTriggers() {
  var triggers = ScriptApp.getProjectTriggers();
  for (var i = 0; i < triggers.length; i++) {
    ScriptApp.deleteTrigger(triggers[i]);
  }
}

function triggerMainWork18() {
  var chatId = getChatId();
  if (chatId) sendMainWorkPrompt(chatId);
}

function triggerSecondJob00() {
  var chatId = getChatId();
  if (chatId) sendSecondJobPrompt(chatId);
}

function triggerPayday10() {
  var day = parseInt(Utilities.formatDate(new Date(), 'Europe/Moscow', 'd'), 10);
  if (day === 10 || day === 25) {
    var chatId = getChatId();
    if (chatId) sendPaydayPrompt(chatId);
  }
}

function triggerReminderMain19() {
  var chatId = getChatId();
  if (!chatId) return;
  var today = getTodayMsk();
  if (!hasMainWorkLogForDate(today)) sendReminderMainWork(chatId);
}

function triggerReminderSecond00() {
  var chatId = getChatId();
  if (!chatId) return;
  var yesterday = getYesterdayMsk();
  if (!hasOrdersForDate(yesterday)) sendReminderSecondJob(chatId);
}

function triggerProdCalendar1st() {
  try {
    ensureProdCalendarUpdated();
  } catch (e) {
    logErrorWithException('triggerProdCalendar1st', e);
  }
}
