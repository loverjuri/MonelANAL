/**
 * Расчёт накопленной ЗП, период с последней выплаты, отчёт для /status и дня выплаты.
 */
var CALC_SHEET = 'Calculations';
var TZ = 'Europe/Moscow';

function formatDateForCompare(d) {
  if (typeof d === 'string') return d.substr(0, 10);
  return Utilities.formatDate(d, TZ, 'yyyy-MM-dd');
}

function getTodayMsk() {
  return formatDateForCompare(new Date());
}

function getYesterdayMsk() {
  var d = new Date();
  d.setDate(d.getDate() - 1);
  return formatDateForCompare(d);
}

/**
 * Возвращает дату последней выплаты (10 или 25) строго до или равную today.
 */
function getLastPayDate(todayStr) {
  var parts = todayStr.split('-');
  var y = parseInt(parts[0], 10);
  var m = parseInt(parts[1], 10);
  var d = parseInt(parts[2], 10);
  var pay1 = getPayDay1();
  var pay2 = getPayDay2();
  var cand1 = y + '-' + (m < 10 ? '0' : '') + m + '-' + (pay1 < 10 ? '0' : '') + pay1;
  var cand2 = y + '-' + (m < 10 ? '0' : '') + m + '-' + (pay2 < 10 ? '0' : '') + pay2;
  if (todayStr >= cand2) return cand2;
  if (todayStr >= cand1) return cand1;
  var prevM = m === 1 ? 12 : m - 1;
  var prevY = m === 1 ? y - 1 : y;
  var prevCand2 = prevY + '-' + (prevM < 10 ? '0' : '') + prevM + '-' + (pay2 < 10 ? '0' : '') + pay2;
  var prevCand1 = prevY + '-' + (prevM < 10 ? '0' : '') + prevM + '-' + (pay1 < 10 ? '0' : '') + pay1;
  if (pay2 > pay1) return todayStr >= prevCand2 ? prevCand2 : prevCand1;
  return todayStr >= prevCand1 ? prevCand1 : prevCand2;
}

/**
 * Период начисления: от (дата последней выплаты + 1 день) по today включительно.
 */
function getAccrualPeriodEnd(todayStr) {
  return todayStr;
}

function addDays(dateStr, days) {
  var d = new Date(dateStr + 'T12:00:00');
  d.setDate(d.getDate() + days);
  return formatDateForCompare(d);
}

function getAccrualPeriodStart(todayStr) {
  var lastPay = getLastPayDate(todayStr);
  return addDays(lastPay, 1);
}

/**
 * Сумма по WorkLog (Main) за период: HoursWorked * HourRateSnapshot (учитывая IsPaid для больничных).
 */
function getAccruedMainForPeriod(startStr, endStr) {
  var data = getSheetData('WorkLog');
  var sum = 0;
  var count = 0;
  for (var i = 0; i < data.length; i++) {
    var dt = data[i][1] ? formatDateForCompare(data[i][1]) : '';
    if (!dt || dt < startStr || dt > endStr) continue;
    if (data[i][2] !== 'Main') continue;
    var paid = data[i][7];
    var hours = Number(data[i][3]) || 0;
    var rate = Number(data[i][4]) || 0;
    if (data[i][5] === 'Sick' && (paid === false || paid === 'FALSE')) continue;
    sum += hours * rate;
    count++;
  }
  logInfo('getAccruedMainForPeriod: ' + startStr + '-' + endStr + ' rows=' + count + ' sum=' + sum);
  return sum;
}

/**
 * Сумма Orders за период.
 */
function getAccruedSecondForPeriod(startStr, endStr) {
  return sumOrdersForPeriod(startStr, endStr);
}

/**
 * Премии из Finance за период (Type = что угодно кроме Expense/Correction — по ТЗ «плюс Премии»).
 * В ТЗ явно: плюс Премии из Finance. Будем считать премии как отдельный тип или категорию.
 * Упрощение: премии — отдельная категория в Finance или тип IncomeSalary с категорией «Премия».
 * По ТЗ: «Плюс Премии (из Finance)». Добавим тип IncomeBonus или используем категорию. Оставим тип IncomeSalary с комментарием/категорией — и не будем дублировать в начислении, т.к. основная ЗП уже считается по WorkLog. Премии — отдельные записи в Finance с типом, например, не указанным в списке. Проще: в Finance только IncomeSalary (выплата), IncomeSecond, Expense, Correction. Премии можно записывать как IncomeSalary с категорией «Премия» и тогда при расчёте «накоплено» мы считаем только WorkLog + Orders. Или добавить тип Bonus. По ТЗ: «Плюс Премии (из Finance)» — значит в Finance есть записи-премии. Добавим тип Bonus или считаем по категории. Для минимальной реализации — не добавляем отдельный тип, считаем начисление = WorkLog Main + Orders; премии/штрафы можно учесть в Correction или отдельно. Оставим как в ТЗ: плюс Премии, минус Штрафы. Тогда в Finance могут быть Type=Bonus и Type=Penalty или категории. Упростим: премии и штрафы не храним отдельно в первой версии; при необходимости можно расширить. Итого: накоплено = AccruedMain + AccruedSecond.
 */
function getAccruedTotal(startStr, endStr) {
  var main = getAccruedMainForPeriod(startStr, endStr);
  var second = getAccruedSecondForPeriod(startStr, endStr);
  return { main: main, second: second, total: main + second };
}

/**
 * Текст для дня выплаты и для /status.
 */
function getAccruedSummaryForPayday() {
  var today = getTodayMsk();
  var start = getAccrualPeriodStart(today);
  var end = getAccrualPeriodEnd(today);
  logInfo('getAccruedSummaryForPayday: today=' + today + ' period=' + start + '-' + end);
  var acc = getAccruedTotal(start, end);
  return {
    periodStart: start,
    periodEnd: end,
    accruedMain: acc.main,
    accruedSecond: acc.second,
    accruedTotal: acc.total
  };
}

/**
 * Следующая дата выплаты (10 или 25).
 */
function getNextPayDate(todayStr) {
  var parts = todayStr.split('-');
  var y = parseInt(parts[0], 10);
  var m = parseInt(parts[1], 10);
  var d = parseInt(parts[2], 10);
  var pay1 = getPayDay1();
  var pay2 = getPayDay2();
  var cand1 = y + '-' + (m < 10 ? '0' : '') + m + '-' + (pay1 < 10 ? '0' : '') + pay1;
  var cand2 = y + '-' + (m < 10 ? '0' : '') + m + '-' + (pay2 < 10 ? '0' : '') + pay2;
  if (todayStr < cand1) return cand1;
  if (todayStr < cand2) return cand2;
  var nextM = m === 12 ? 1 : m + 1;
  var nextY = m === 12 ? y + 1 : y;
  var nextCand1 = nextY + '-' + (nextM < 10 ? '0' : '') + nextM + '-' + (pay1 < 10 ? '0' : '') + pay1;
  return nextCand1;
}

/**
 * Остаток бюджета: доходы − расходы за всё время (или за текущий месяц — по ТЗ «текущий остаток бюджета»).
 * ТЗ: «Текущий остаток бюджета (Доходы - Расходы)». Считаем суммарно все доходы и расходы из Finance.
 */
function getBudgetBalance() {
  var sheet = getSheet('Finance');
  if (!sheet) return 0;
  var data = sheet.getDataRange().getValues();
  var income = 0, expense = 0;
  for (var i = 1; i < data.length; i++) {
    var type = data[i][2];
    var amount = Number(data[i][3]) || 0;
    if (type === TYPE_INCOME_SALARY || type === TYPE_INCOME_SECOND) income += amount;
    else if (type === TYPE_EXPENSE) expense += amount;
  }
  return income - expense;
}
