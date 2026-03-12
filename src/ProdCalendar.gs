/**
 * Производственный календарь РФ через API isdayoff.ru.
 * Коды: 0 — рабочий (8ч), 1 — выходной (0ч), 2 — сокращённый (7ч).
 */
var PROD_CALENDAR_SHEET = 'ProdCalendar';
var ISDAYOFF_API = 'https://isdayoff.ru/api/getdata';

function fetchMonthCalendar(year, month) {
  var url = ISDAYOFF_API + '?year=' + year + '&month=' + month + '&cc=ru&pre=1';
  try {
    var response = UrlFetchApp.fetch(url, { muteHttpExceptions: true });
    var text = response.getContentText();
    // API возвращает строку кодов по одному на день (без разделителей или с \n)
    var codes = text.replace(/\s/g, '').split('');
    return codes;
  } catch (e) {
    logErrorWithException('ProdCalendar fetchMonthCalendar', e);
    return [];
  }
}

function codeToWorkHours(code) {
  if (code === '0') return 8;
  if (code === '2') return 7;
  return 0;
}

function codeToIsWorking(code) {
  return code === '0' || code === '2';
}

/**
 * Заполняет лист ProdCalendar на указанный месяц. Пакетная запись.
 */
function fillProdCalendarForMonth(year, month) {
  var codes = fetchMonthCalendar(year, month);
  if (codes.length === 0) return;
  var lastDay = new Date(year, month, 0).getDate();
  var rows = [];
  var monthNorm = 0;
  for (var d = 1; d <= lastDay; d++) {
    var code = codes[d - 1] || '1';
    var hours = codeToWorkHours(code);
    monthNorm += hours;
    var dateStr = Utilities.formatDate(new Date(year, month - 1, d), 'Europe/Moscow', 'yyyy-MM-dd');
    rows.push([dateStr, codeToIsWorking(code), hours, null]);
  }
  // Заполняем MonthNormHours для каждой строки
  for (var i = 0; i < rows.length; i++) {
    rows[i][3] = monthNorm;
  }
  var sheet = getSheet(PROD_CALENDAR_SHEET);
  if (!sheet) return;
  var existing = sheet.getDataRange().getValues();
  var existingDates = {};
  if (existing.length > 1) {
    for (var j = 1; j < existing.length; j++) {
      existingDates[String(existing[j][0])] = true;
    }
  }
  var toAppend = [];
  for (var k = 0; k < rows.length; k++) {
    if (!existingDates[rows[k][0]]) toAppend.push(rows[k]);
  }
  if (toAppend.length > 0) {
    var lastRow = sheet.getLastRow();
    sheet.getRange(lastRow + 1, 1, toAppend.length, 4).setValues(toAppend);
  }
}

/**
 * Обновляет календарь на текущий и следующий месяц. Вызывать 1-го числа или при первом обращении.
 */
function ensureProdCalendarUpdated() {
  var now = new Date();
  var tz = 'Europe/Moscow';
  var year = parseInt(Utilities.formatDate(now, tz, 'yyyy'), 10);
  var month = parseInt(Utilities.formatDate(now, tz, 'MM'), 10);
  fillProdCalendarForMonth(year, month);
  var nextMonth = month === 12 ? 1 : month + 1;
  var nextYear = month === 12 ? year + 1 : year;
  fillProdCalendarForMonth(nextYear, nextMonth);
}

/**
 * Возвращает норму часов в месяце для даты (год-месяц). Читает из листа или кэша.
 */
function getMonthNormHoursForDate(dateStr) {
  var parts = dateStr.split('-');
  if (parts.length < 2) return getWorkHoursNorm() * 21;
  var year = parseInt(parts[0], 10);
  var month = parseInt(parts[1], 10);
  var cache = CacheService.getScriptCache();
  var key = 'month_norm_' + year + '_' + month;
  var cached = cache.get(key);
  if (cached) return Number(cached);
  var sheet = getSheet(PROD_CALENDAR_SHEET);
  if (!sheet) return getWorkHoursNorm() * 21;
  var data = sheet.getDataRange().getValues();
  for (var i = 1; i < data.length; i++) {
    var row = data[i];
    if (row[0] && String(row[0]).indexOf(parts[0] + '-' + (month < 10 ? '0' : '') + month) === 0 && row[3] != null) {
      cache.put(key, String(row[3]), 600);
      return Number(row[3]);
    }
  }
  ensureProdCalendarUpdated();
  data = sheet.getDataRange().getValues();
  for (var j = 1; j < data.length; j++) {
    var r = data[j];
    if (r[0] && String(r[0]).indexOf(parts[0] + '-' + (month < 10 ? '0' : '') + month) === 0 && r[3] != null) {
      cache.put(key, String(r[3]), 600);
      return Number(r[3]);
    }
  }
  return getWorkHoursNorm() * 21;
}
