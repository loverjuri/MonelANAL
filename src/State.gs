/**
 * FSM: хранение состояния диалога в листе State.
 * Столбцы: ChatID, Scenario, Step, Payload (JSON), UpdatedAt.
 */
var STATE_SHEET = 'State';

function getStateSheet() {
  return getSheet(STATE_SHEET);
}

function getState(chatId) {
  var sheet = getStateSheet();
  if (!sheet) return null;
  var data = sheet.getDataRange().getValues();
  var chatStr = String(chatId);
  for (var i = 1; i < data.length; i++) {
    if (String(data[i][0]) === chatStr) {
      var payload = {};
      try {
        if (data[i][3]) payload = JSON.parse(data[i][3]);
      } catch (e) {}
      return {
        scenario: data[i][1],
        step: data[i][2],
        payload: payload,
        updatedAt: data[i][4]
      };
    }
  }
  return null;
}

function setState(chatId, scenario, step, payload) {
  var sheet = getStateSheet();
  if (!sheet) return;
  var data = sheet.getDataRange().getValues();
  var chatStr = String(chatId);
  var payloadStr = payload ? JSON.stringify(payload) : '{}';
  var now = new Date();
  for (var i = 1; i < data.length; i++) {
    if (String(data[i][0]) === chatStr) {
      sheet.getRange(i + 1, 2, i + 1, 5).setValues([[scenario, step, payloadStr, now]]);
      return;
    }
  }
  sheet.appendRow([chatId, scenario, step, payloadStr, now]);
}

function clearState(chatId) {
  var sheet = getStateSheet();
  if (!sheet) return;
  var data = sheet.getDataRange().getValues();
  var chatStr = String(chatId);
  for (var i = data.length - 1; i >= 1; i--) {
    if (String(data[i][0]) === chatStr) {
      sheet.deleteRow(i + 1);
      return;
    }
  }
}
