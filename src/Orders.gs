/**
 * Заказы второй работы. Один день может содержать несколько заказов.
 */
var ORDERS_SHEET = 'Orders';
var ORDER_STATUS_NEW = 'New';
var ORDER_STATUS_PAID = 'Paid';

function getOrdersSheet() {
  return getSheet(ORDERS_SHEET);
}

function addOrder(dateStr, description, amount) {
  var orderId = generateId();
  var row = [orderId, dateStr, description, amount, ORDER_STATUS_NEW];
  appendRows(ORDERS_SHEET, [row]);
  return orderId;
}

/**
 * Добавить заказ с несколькими позициями (description — объединённое описание).
 */
function addOrderWithItems(dateStr, items) {
  if (!items || items.length === 0) return null;
  var total = 0;
  var descParts = [];
  for (var i = 0; i < items.length; i++) {
    total += Number(items[i].amount) || 0;
    descParts.push((items[i].description || '').trim() + ' — ' + (items[i].amount || 0));
  }
  var description = descParts.join('; ');
  return addOrder(dateStr, description, total);
}

function getOrdersForPeriod(startDateStr, endDateStr) {
  var data = getSheetData(ORDERS_SHEET);
  var result = [];
  for (var i = 0; i < data.length; i++) {
    var dt = data[i][1] ? formatDateForCompare(data[i][1]) : '';
    if (dt && dt >= startDateStr && dt <= endDateStr) {
      result.push({ orderId: data[i][0], date: dt, description: data[i][2], amount: Number(data[i][3]) || 0, status: data[i][4] });
    }
  }
  return result;
}

function sumOrdersForPeriod(startDateStr, endDateStr) {
  var orders = getOrdersForPeriod(startDateStr, endDateStr);
  var sum = 0;
  for (var j = 0; j < orders.length; j++) sum += orders[j].amount;
  return sum;
}

/**
 * Есть ли хотя бы один заказ или явный ответ «нет доходов» за дату — храним в State или проверяем заказы.
 * Для напоминания 00:30: если заказов за вчера нет и State не «нет доходов» — напомнить.
 */
function hasOrdersForDate(dateStr) {
  var data = getSheetData(ORDERS_SHEET);
  var dateStrNorm = dateStr.length >= 10 ? dateStr.substr(0, 10) : dateStr;
  for (var i = 0; i < data.length; i++) {
    var dt = data[i][1] ? formatDateForCompare(data[i][1]) : '';
    if (dt === dateStrNorm) return true;
  }
  return false;
}
