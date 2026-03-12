/**
 * Журнал рабочего времени. HourRateSnapshot фиксируется при записи.
 * Статусы: Work, Sick, Vacation, WeekendWork.
 */
var WORKLOG_SHEET = 'WorkLog';
var JOB_MAIN = 'Main';
var JOB_SECOND = 'Second';
var STATUS_WORK = 'Work';
var STATUS_SICK = 'Sick';
var STATUS_VACATION = 'Vacation';
var STATUS_WEEKEND_WORK = 'WeekendWork';

function getWorkLogSheet() {
  return getSheet(WORKLOG_SHEET);
}

/**
 * Стоимость часа на дату: FixedSalary / MonthNormHours для месяца этой даты.
 */
function calcHourRateSnapshotForDate(dateStr) {
  var norm = getMonthNormHoursForDate(dateStr);
  if (norm <= 0) norm = getWorkHoursNorm() * 21;
  var salary = getFixedSalary();
  return salary / norm;
}

/**
 * Для больничного: последняя запись Sick по Main, если дата предыдущего дня — index+1, иначе 1.
 */
function getNextSickDayIndex(dateStr) {
  var sheet = getWorkLogSheet();
  if (!sheet) return 1;
  var data = sheet.getDataRange().getValues();
  if (data.length <= 1) return 1;
  var prevIndex = 0;
  for (var i = data.length - 1; i >= 1; i--) {
    var row = data[i];
    if (row[2] !== JOB_MAIN) continue;
    if (row[5] !== STATUS_SICK) break;
    var rowDate = row[1] ? formatDateForCompare(row[1]) : '';
    if (!rowDate) continue;
    var rowTime = new Date(rowDate).getTime();
    var currentTime = new Date(dateStr).getTime();
    var dayMs = 24 * 60 * 60 * 1000;
    if (currentTime - rowTime === dayMs) {
      prevIndex = row[6] ? parseInt(row[6], 10) : 1;
      return prevIndex + 1;
    }
    break;
  }
  return 1;
}

/**
 * Добавляет запись в WorkLog. Пакетная запись одной строки.
 */
function addWorkLogEntry(dateStr, jobType, hoursWorked, status) {
  var hourRate = calcHourRateSnapshotForDate(dateStr);
  var sickDayIndex = '';
  var isPaid = true;
  if (status === STATUS_SICK) {
    sickDayIndex = getNextSickDayIndex(dateStr);
    isPaid = sickDayIndex <= 3;
  }
  var id = generateId();
  var createdAt = new Date();
  var row = [id, dateStr, jobType, hoursWorked, hourRate, status, sickDayIndex, isPaid, createdAt];
  appendRows(WORKLOG_SHEET, [row]);
  return id;
}

function hasWorkLogForDate(dateStr, jobType) {
  var data = getSheetData(WORKLOG_SHEET);
  var dateStrNorm = dateStr.length >= 10 ? dateStr.substr(0, 10) : dateStr;
  for (var i = 0; i < data.length; i++) {
    var d = data[i][1];
    var dt = d ? formatDateForCompare(d) : '';
    if (dt === dateStrNorm && (!jobType || data[i][2] === jobType)) return true;
  }
  return false;
}

/**
 * Есть ли запись по основной работе за указанную дату (для напоминания 19:00).
 */
function hasMainWorkLogForDate(dateStr) {
  return hasWorkLogForDate(dateStr, JOB_MAIN);
}
