/**
 * Запись в лист Logs. Уровни: Info, Error.
 * Все вызовы — через try/catch в вызывающем коде.
 */
var LOG_SHEET_NAME = 'Logs';

function logInfo(message) {
  try {
    var ss = getSpreadsheet();
    if (!ss) return;
    var sheet = getOrCreateSheet(ss, LOG_SHEET_NAME);
    if (sheet.getLastRow() === 0) {
      sheet.getRange(1, 1, 1, 3).setValues([['Timestamp', 'Level', 'Message']]);
    }
    appendRows(LOG_SHEET_NAME, [[new Date(), 'Info', message]]);
  } catch (e) {
    Logger.log('[Info] ' + message);
  }
}

function logError(message) {
  try {
    var ss = getSpreadsheet();
    if (!ss) return;
    var sheet = getOrCreateSheet(ss, LOG_SHEET_NAME);
    if (sheet.getLastRow() === 0) {
      sheet.getRange(1, 1, 1, 3).setValues([['Timestamp', 'Level', 'Message']]);
    }
    appendRows(LOG_SHEET_NAME, [[new Date(), 'Error', message]]);
  } catch (e) {
    Logger.log('[Error] ' + message);
  }
}

function logErrorWithException(message, err) {
  var fullMessage = message + (err && err.message ? ': ' + err.message : '');
  logError(fullMessage);
}
