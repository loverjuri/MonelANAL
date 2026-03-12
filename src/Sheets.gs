/**
 * Общие хелперы для работы с Google Таблицей.
 * Все записи — пакетные (setValues/appendRow массивов).
 */

function getSpreadsheet() {
  return SpreadsheetApp.getActiveSpreadsheet();
}

function getSheet(name) {
  var ss = getSpreadsheet();
  var sheet = ss.getSheetByName(name);
  if (!sheet) return null;
  return sheet;
}

function getOrCreateSheet(ss, name) {
  var sheet = ss.getSheetByName(name);
  if (sheet) return sheet;
  return ss.insertSheet(name);
}

/**
 * Читает все данные листа (без заголовка) как массив строк.
 * Первая строка считается заголовком.
 */
function getSheetData(sheetName) {
  var sheet = getSheet(sheetName);
  if (!sheet) return [];
  var range = sheet.getDataRange();
  var data = range.getValues();
  if (data.length <= 1) return [];
  return data.slice(1);
}

/**
 * Читает лист и возвращает объект: { headers: [], rows: [] }
 */
function getSheetWithHeaders(sheetName) {
  var sheet = getSheet(sheetName);
  if (!sheet) return { headers: [], rows: [] };
  var range = sheet.getDataRange();
  var data = range.getValues();
  if (data.length === 0) return { headers: [], rows: [] };
  return {
    headers: data[0],
    rows: data.length > 1 ? data.slice(1) : []
  };
}

/**
 * Добавляет строки пакетно в конец листа.
 * @param {string} sheetName
 * @param {Array<Array>} rows — массив строк (каждая строка — массив значений)
 */
function appendRows(sheetName, rows) {
  if (!rows || rows.length === 0) return;
  var sheet = getSheet(sheetName);
  if (!sheet) return;
  var lastRow = sheet.getLastRow();
  var startRow = lastRow + 1;
  sheet.getRange(startRow, 1, rows.length, rows[0].length).setValues(rows);
}

/**
 * Инициализация листов и заголовков (вызвать один раз при первом запуске).
 */
function initSheetIfNeeded() {
  var ss = getSpreadsheet();
  var configs = [
    { name: 'Config', headers: ['Parameter', 'Value'] },
    { name: 'ProdCalendar', headers: ['Date', 'IsWorking', 'WorkHoursNorm', 'MonthNormHours'] },
    { name: 'WorkLog', headers: ['ID', 'Date', 'JobType', 'HoursWorked', 'HourRateSnapshot', 'Status', 'SickDayIndex', 'IsPaid', 'CreatedAt'] },
    { name: 'Orders', headers: ['OrderID', 'Date', 'Description', 'Amount', 'Status'] },
    { name: 'Finance', headers: ['ID', 'Date', 'Type', 'Amount', 'Category', 'Comment'] },
    { name: 'Calculations', headers: ['PeriodStart', 'PeriodEnd', 'AccruedSalary', 'ReceivedSalary', 'Difference'] },
    { name: 'State', headers: ['ChatID', 'Scenario', 'Step', 'Payload', 'UpdatedAt'] },
    { name: 'Logs', headers: ['Timestamp', 'Level', 'Message'] }
  ];
  configs.forEach(function (c) {
    var sheet = getOrCreateSheet(ss, c.name);
    if (sheet.getLastRow() === 0) {
      sheet.getRange(1, 1, 1, c.headers.length).setValues([c.headers]);
    }
  });
}

/**
 * Заполняет лист Config строками по умолчанию, если в нём только заголовок.
 * Вызвать после initSheetIfNeeded() при первом запуске.
 */
function initConfigDefaultsIfEmpty() {
  var sheet = getSheet('Config');
  if (!sheet || sheet.getLastRow() >= 2) return;
  var defaults = [
    ['FixedSalary', '100000'],
    ['SecondJobPercent', '10'],
    ['PayDay1', '10'],
    ['PayDay2', '25'],
    ['WorkHoursNorm', '8'],
    ['ChatID', ''],
    ['TimeZone', 'Europe/Moscow']
  ];
  if (sheet.getLastRow() === 0) {
    sheet.getRange(1, 1, 1, 2).setValues([['Parameter', 'Value']]);
  }
  var startRow = sheet.getLastRow() + 1;
  sheet.getRange(startRow, 1, defaults.length, 2).setValues(defaults);
}

function generateId() {
  return Utilities.getUuid();
}
