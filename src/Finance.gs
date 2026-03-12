/**
 * Финансы: доходы, расходы, корректировки.
 * Типы: IncomeSalary, IncomeSecond, Expense, Correction.
 */
var FINANCE_SHEET = 'Finance';
var TYPE_INCOME_SALARY = 'IncomeSalary';
var TYPE_INCOME_SECOND = 'IncomeSecond';
var TYPE_EXPENSE = 'Expense';
var TYPE_CORRECTION = 'Correction';

var EXPENSE_CATEGORIES = ['Еда', 'Транспорт', 'ЗП Выплата', 'Жильё', 'Здоровье', 'Развлечения', 'Прочее'];

function getFinanceSheet() {
  return getSheet(FINANCE_SHEET);
}

function addFinanceEntry(dateStr, type, amount, category, comment) {
  var id = generateId();
  var row = [id, dateStr, type, amount, category || '', comment || ''];
  appendRows(FINANCE_SHEET, [row]);
  return id;
}

function getFinanceForPeriod(startDateStr, endDateStr) {
  var data = getSheetData(FINANCE_SHEET);
  var result = [];
  for (var i = 0; i < data.length; i++) {
    var dt = data[i][1] ? formatDateForCompare(data[i][1]) : '';
    if (dt && dt >= startDateStr && dt <= endDateStr) {
      result.push({
        id: data[i][0],
        date: dt,
        type: data[i][2],
        amount: Number(data[i][3]) || 0,
        category: data[i][4],
        comment: data[i][5]
      });
    }
  }
  return result;
}

function getTotalIncomeByPeriod(startDateStr, endDateStr) {
  var rows = getFinanceForPeriod(startDateStr, endDateStr);
  var sum = 0;
  for (var j = 0; j < rows.length; j++) {
    if (rows[j].type === TYPE_INCOME_SALARY || rows[j].type === TYPE_INCOME_SECOND) sum += rows[j].amount;
  }
  return sum;
}

function getTotalExpenseByPeriod(startDateStr, endDateStr) {
  var rows = getFinanceForPeriod(startDateStr, endDateStr);
  var sum = 0;
  for (var k = 0; k < rows.length; k++) {
    if (rows[k].type === TYPE_EXPENSE) sum += rows[k].amount;
  }
  return sum;
}

function recordPaydayReceived(dateStr, amountReceived, accruedMain, accruedSecond, periodStart, periodEnd) {
  addFinanceEntry(dateStr, TYPE_INCOME_SALARY, amountReceived, 'ЗП Выплата', 'Фактически получено');
  var totalAccrued = (accruedMain || 0) + (accruedSecond || 0);
  var diff = totalAccrued - amountReceived;
  if (Math.abs(diff) > 0.01) {
    addFinanceEntry(dateStr, TYPE_CORRECTION, -diff, 'Корректировка', 'Разница начислено/получено');
  }
  if (periodStart && periodEnd) {
    appendRows('Calculations', [[periodStart, periodEnd, totalAccrued, amountReceived, -diff]]);
  }
}
