/**
 * Telegram Bot: отправка сообщений, Inline-кнопки, FSM и сценарии.
 * Все ответы на русском.
 */
var TELEGRAM_API = 'https://api.telegram.org/bot';

function telegramApi(method, payload) {
  var token = getBotToken();
  if (!token) return null;
  var url = TELEGRAM_API + token + '/' + method;
  var options = {
    method: 'post',
    contentType: 'application/json',
    payload: JSON.stringify(payload),
    muteHttpExceptions: true
  };
  try {
    var response = UrlFetchApp.fetch(url, options);
    return JSON.parse(response.getContentText());
  } catch (e) {
    logErrorWithException('telegramApi ' + method, e);
    return null;
  }
}

function sendTelegramMessage(chatId, text, replyMarkup) {
  var body = { chat_id: chatId, text: text };
  if (replyMarkup) body.reply_markup = replyMarkup;
  return telegramApi('sendMessage', body);
}

function answerCallbackQuery(callbackQueryId) {
  return telegramApi('answerCallbackQuery', { callback_query_id: callbackQueryId });
}

function editMessageText(chatId, messageId, text, replyMarkup) {
  var body = { chat_id: chatId, message_id: messageId, text: text };
  if (replyMarkup) body.reply_markup = replyMarkup;
  return telegramApi('editMessageText', body);
}

function buildInlineKeyboard(buttons) {
  return { inline_keyboard: buttons };
}

function buildMainWorkKeyboard() {
  return buildInlineKeyboard([
    [
      { text: 'Полный (8ч)', callback_data: 'main_full' },
      { text: 'Частично', callback_data: 'main_partial' }
    ],
    [
      { text: 'Не работал', callback_data: 'main_none' },
      { text: 'Выходной (работал)', callback_data: 'main_weekend' }
    ],
    [{ text: 'Больничный', callback_data: 'main_sick' }]
  ]);
}

function buildSecondJobKeyboard() {
  return buildInlineKeyboard([
    [{ text: 'Добавить заказ', callback_data: 'second_add' }],
    [
      { text: 'Нет доходов', callback_data: 'second_none' },
      { text: 'Посмотреть статус', callback_data: 'second_status' }
    ]
  ]);
}

function buildExpenseCategoriesKeyboard() {
  var cats = EXPENSE_CATEGORIES;
  var row = [];
  var keyboard = [];
  for (var i = 0; i < cats.length; i++) {
    row.push({ text: cats[i], callback_data: 'exp_cat_' + i });
    if (row.length >= 2) {
      keyboard.push(row);
      row = [];
    }
  }
  if (row.length) keyboard.push(row);
  keyboard.push([{ text: 'Отмена', callback_data: 'cmd_cancel' }]);
  return buildInlineKeyboard(keyboard);
}

function buildYesNoKeyboard() {
  return buildInlineKeyboard([
    [{ text: 'Да', callback_data: 'yes' }, { text: 'Нет', callback_data: 'no' }]
  ]);
}

function buildExpenseCommentKeyboard() {
  return buildInlineKeyboard([
    [{ text: 'Пропустить', callback_data: 'exp_skip' }, { text: 'Отмена', callback_data: 'cmd_cancel' }]
  ]);
}

function buildIncomeCommentKeyboard() {
  return buildInlineKeyboard([
    [{ text: 'Без комментария', callback_data: 'inc_skip' }, { text: 'Отмена', callback_data: 'cmd_cancel' }]
  ]);
}

function buildHoursQuickKeyboard() {
  return buildInlineKeyboard([
    [
      { text: '4 ч', callback_data: 'hours_4' },
      { text: '6 ч', callback_data: 'hours_6' },
      { text: '8 ч', callback_data: 'hours_8' }
    ]
  ]);
}

function buildMainMenuKeyboard() {
  return buildInlineKeyboard([
    [
      { text: 'Статус', callback_data: 'cmd_status' },
      { text: 'Расход', callback_data: 'cmd_expense' }
    ],
    [
      { text: 'Доход', callback_data: 'cmd_income' },
      { text: 'Справка', callback_data: 'cmd_help' }
    ]
  ]);
}

function buildCancelKeyboard() {
  return buildInlineKeyboard([[{ text: 'Отмена', callback_data: 'cmd_cancel' }]]);
}

function isAuthorizedChat(chatId) {
  var allowed = getChatId();
  if (!allowed) return true;
  return String(chatId) === String(allowed);
}

function buildReplyKeyboard() {
  return {
    keyboard: [
      [{ text: 'Статус' }, { text: 'Расход' }],
      [{ text: 'Доход' }, { text: 'Справка' }]
    ],
    resize_keyboard: true,
    one_time_keyboard: false
  };
}

function processUpdate(update) {
  var chatId = null;
  logInfo('Bot started');
  try {
    if (update.message) {
      chatId = update.message.chat.id;
      if (!isAuthorizedChat(chatId)) {
        sendTelegramMessage(chatId,
          'Ваш Chat ID (' + chatId + ') не в списке разрешённых. Добавьте его в лист Config (параметр ChatID) или в свойства скрипта (CHAT_ID).');
        return;
      }
      handleMessage(chatId, update.message.text || '', update.message.message_id);
      return;
    }
    if (update.callback_query) {
      chatId = update.callback_query.message.chat.id;
      if (!isAuthorizedChat(chatId)) {
        answerCallbackQuery(update.callback_query.id);
        sendTelegramMessage(chatId,
          'Ваш Chat ID (' + chatId + ') не в списке разрешённых. Добавьте его в Config.');
        return;
      }
      handleCallbackQuery(
        chatId,
        update.callback_query.id,
        update.callback_query.data,
        update.callback_query.message.message_id
      );
    }
  } catch (e) {
    logErrorWithException('processUpdate', e);
    if (chatId) {
      sendTelegramMessage(chatId, 'Произошла ошибка. Проверьте журнал выполнения и лист Logs.');
    }
  }
}

function isExitCommand(text) {
  var t = (text || '').trim().toLowerCase();
  return t === '/start' || t === '/help' || t === '/помощь' || t === 'справка' || t === 'отмена' || t === '/cancel' || t === 'статус' || t === 'расход' || t === 'доход';
}

function handleMessage(chatId, text, messageId) {
  var state = getState(chatId);
  var trimmed = (text || '').trim();
  if (trimmed) logInfo('handleMessage: chatId=' + chatId + ' text=' + trimmed.substring(0, 50));

  if (state && isExitCommand(trimmed)) {
    clearState(chatId);
    sendTelegramMessage(chatId, 'Выберите действие:', buildMainMenuKeyboard());
    return;
  }

  if (state && state.scenario === 'main_hours') {
    var hours = parseFloat(trimmed.replace(',', '.'), 10);
    if (!isNaN(hours) && hours >= 0 && hours <= 24) {
      var dateStr = state.payload.date || getTodayMsk();
      var isWeekend = state.payload.weekend === true;
      addWorkLogEntry(dateStr, JOB_MAIN, hours, isWeekend ? STATUS_WEEKEND_WORK : STATUS_WORK);
      clearState(chatId);
      sendTelegramMessage(chatId, 'Записано: ' + hours + ' ч.');
      return;
    }
    sendTelegramMessage(chatId, 'Введите число часов от 0 до 24.');
    return;
  }

  if (state && state.scenario === 'second_order') {
    if (state.step === 'description') {
      setState(chatId, 'second_order', 'amount', { date: state.payload.date, description: trimmed });
      sendTelegramMessage(chatId, 'Введите сумму заказа (число):');
      return;
    }
    if (state.step === 'amount') {
      var amount = parseFloat(trimmed.replace(/[\s]/g, '').replace(',', '.'), 10);
      if (!isNaN(amount) && amount >= 0) {
        var desc = state.payload.description || '';
        var items = state.payload.items || [];
        items.push({ description: desc, amount: amount });
        setState(chatId, 'second_order', 'more', { date: state.payload.date, items: items });
        sendTelegramMessage(chatId, 'Ещё позиции в этот заказ?', buildYesNoKeyboard());
        return;
      }
      sendTelegramMessage(chatId, 'Введите число (сумма).');
      return;
    }
  }

  if (state && state.scenario === 'second_order' && state.step === 'more') {
    if (trimmed === 'да' || trimmed === 'нет') {
      if (trimmed === 'нет') {
        addOrderWithItems(state.payload.date, state.payload.items || []);
        clearState(chatId);
        sendTelegramMessage(chatId, 'Заказ сохранён.');
        return;
      }
      setState(chatId, 'second_order', 'description', { date: state.payload.date, items: state.payload.items || [] });
      sendTelegramMessage(chatId, 'Введите описание следующей позиции:');
      return;
    }
  }

  if (state && state.scenario === 'payday_amount') {
    var received = parseFloat(trimmed.replace(/[\s]/g, '').replace(',', '.'), 10);
    if (!isNaN(received) && received >= 0) {
      var acc = state.payload.accrued || {};
      recordPaydayReceived(getTodayMsk(), received, acc.main, acc.second, state.payload.periodStart, state.payload.periodEnd);
      clearState(chatId);
      sendTelegramMessage(chatId, 'Сумма ' + received + ' руб. записана. Корректировка при необходимости внесена.');
      return;
    }
    sendTelegramMessage(chatId, 'Введите число (сумма, полученная на карту).');
    return;
  }

  if (state && state.scenario === 'expense_comment') {
    var amount = state.payload.amount;
    var category = state.payload.category;
    var comment = (trimmed === '-' || trimmed === 'пропустить' || trimmed === 'нет') ? '' : trimmed;
    addFinanceEntry(getTodayMsk(), TYPE_EXPENSE, amount, category, comment);
    clearState(chatId);
    sendTelegramMessage(chatId, 'Расход записан: ' + amount + ' руб., ' + category + (comment ? ', ' + comment : '') + '.');
    return;
  }

  if (state && state.scenario === 'expense_amount') {
    var amt = parseFloat(trimmed.replace(/[\s]/g, '').replace(',', '.'), 10);
    if (!isNaN(amt) && amt > 0) {
      setState(chatId, 'expense_cat', '0', { amount: amt });
      sendTelegramMessage(chatId, 'Выберите категорию:', buildExpenseCategoriesKeyboard());
      return;
    }
    sendTelegramMessage(chatId, 'Введите сумму расхода (положительное число).', buildCancelKeyboard());
    return;
  }

  if (state && state.scenario === 'income_comment') {
    var amount = state.payload.amount;
    var comment = (trimmed === '-' || trimmed === 'пропустить' || trimmed === 'нет') ? '' : trimmed;
    addFinanceEntry(getTodayMsk(), TYPE_INCOME_SECOND, amount, 'Прочее', comment);
    clearState(chatId);
    sendTelegramMessage(chatId, 'Доход записан: ' + amount + ' руб.' + (comment ? ' (' + comment + ')' : '') + '.');
    return;
  }

  if (state && state.scenario === 'income_amount') {
    var amt = parseFloat(trimmed.replace(/[\s]/g, '').replace(',', '.'), 10);
    if (!isNaN(amt) && amt > 0) {
      setState(chatId, 'income_comment', '0', { amount: amt });
      sendTelegramMessage(chatId, 'Комментарий к доходу:', buildIncomeCommentKeyboard());
      return;
    }
    sendTelegramMessage(chatId, 'Введите сумму дохода (положительное число).', buildCancelKeyboard());
    return;
  }

  if (trimmed === '/status' || trimmed === '/статус' || trimmed === 'Статус') {
    handleStatus(chatId);
    return;
  }

  if (trimmed === '/expense' || trimmed === '/расход' || trimmed === 'Расход') {
    setState(chatId, 'expense_amount', '0', {});
    sendTelegramMessage(chatId, 'Введите сумму расхода:', buildCancelKeyboard());
    return;
  }

  if (trimmed === '/income' || trimmed === '/доход' || trimmed === 'Доход') {
    setState(chatId, 'income_amount', '0', {});
    sendTelegramMessage(chatId, 'Введите сумму дохода:', buildCancelKeyboard());
    return;
  }

  if (trimmed === '/start') {
    sendTelegramMessage(chatId, 'Добро пожаловать! Выберите действие:', buildMainMenuKeyboard());
    return;
  }
  if (trimmed === '/help' || trimmed === '/помощь' || trimmed === 'Справка' || trimmed === '') {
    sendTelegramMessage(chatId, 'Выберите действие:', buildMainMenuKeyboard());
    return;
  }

  if (state) clearState(chatId);
  sendTelegramMessage(chatId, 'Выберите действие:', buildMainMenuKeyboard());
}

function handleCallbackQuery(chatId, callbackQueryId, data, messageId) {
  answerCallbackQuery(callbackQueryId);

  if (data === 'cmd_status') {
    handleStatus(chatId);
    return;
  }
  if (data === 'cmd_expense') {
    setState(chatId, 'expense_amount', '0', {});
    sendTelegramMessage(chatId, 'Введите сумму расхода:', buildCancelKeyboard());
    return;
  }
  if (data === 'cmd_income') {
    setState(chatId, 'income_amount', '0', {});
    sendTelegramMessage(chatId, 'Введите сумму дохода:', buildCancelKeyboard());
    return;
  }
  if (data === 'cmd_help') {
    handleHelp(chatId);
    return;
  }
  if (data === 'cmd_cancel') {
    clearState(chatId);
    sendTelegramMessage(chatId, 'Отменено. Выберите действие:', buildMainMenuKeyboard());
    return;
  }

  if (data === 'main_full') {
    addWorkLogEntry(getTodayMsk(), JOB_MAIN, 8, STATUS_WORK);
    sendTelegramMessage(chatId, 'Записано: полный день (8 ч).');
    return;
  }
  if (data === 'main_none') {
    sendTelegramMessage(chatId, 'Ок, не работал.');
    return;
  }
  if (data === 'main_partial') {
    setState(chatId, 'main_hours', '0', { date: getTodayMsk(), weekend: false });
    sendTelegramMessage(chatId, 'Часы или выберите:', buildHoursQuickKeyboard());
    return;
  }
  if (data === 'main_weekend') {
    setState(chatId, 'main_hours', '0', { date: getTodayMsk(), weekend: true });
    sendTelegramMessage(chatId, 'Часы в выходной или выберите:', buildHoursQuickKeyboard());
    return;
  }
  if (data === 'main_sick') {
    addWorkLogEntry(getTodayMsk(), JOB_MAIN, 0, STATUS_SICK);
    sendTelegramMessage(chatId, 'Записан день больничного (первые 3 дня оплачиваются, с 4-го — нет).');
    return;
  }

  if (data === 'second_add') {
    var yesterday = getYesterdayMsk();
    setState(chatId, 'second_order', 'description', { date: yesterday, items: [] });
    sendTelegramMessage(chatId, 'Введите описание заказа (что сделано):');
    return;
  }
  if (data === 'second_none') {
    addOrder(getYesterdayMsk(), 'Нет доходов', 0);
    sendTelegramMessage(chatId, 'Ок, доходов нет.');
    return;
  }
  if (data === 'second_status') {
    handleSecondJobStatus(chatId);
    return;
  }

  if (data === 'yes' || data === 'no') {
    var st = getState(chatId);
    if (st && st.scenario === 'second_order' && st.step === 'more') {
      if (data === 'no') {
        addOrderWithItems(st.payload.date, st.payload.items || []);
        clearState(chatId);
        sendTelegramMessage(chatId, 'Заказ сохранён.');
      } else {
        setState(chatId, 'second_order', 'description', { date: st.payload.date, items: st.payload.items || [] });
        sendTelegramMessage(chatId, 'Введите описание следующей позиции:');
      }
    }
    return;
  }

  if (data.indexOf('exp_cat_') === 0) {
    var idx = parseInt(data.replace('exp_cat_', ''), 10);
    var cat = EXPENSE_CATEGORIES[idx];
    var s = getState(chatId);
    if (s && s.scenario === 'expense_cat' && s.payload.amount != null) {
      setState(chatId, 'expense_comment', '0', { amount: s.payload.amount, category: cat });
      sendTelegramMessage(chatId, 'Комментарий к расходу:', buildExpenseCommentKeyboard());
    }
    return;
  }

  if (data === 'exp_skip') {
    var s = getState(chatId);
    if (s && s.scenario === 'expense_comment') {
      addFinanceEntry(getTodayMsk(), TYPE_EXPENSE, s.payload.amount, s.payload.category, '');
      clearState(chatId);
      sendTelegramMessage(chatId, 'Расход записан: ' + s.payload.amount + ' руб., ' + s.payload.category + '.');
    }
    return;
  }

  if (data === 'inc_skip') {
    var s = getState(chatId);
    if (s && s.scenario === 'income_comment') {
      addFinanceEntry(getTodayMsk(), TYPE_INCOME_SECOND, s.payload.amount, 'Прочее', '');
      clearState(chatId);
      sendTelegramMessage(chatId, 'Доход записан: ' + s.payload.amount + ' руб.');
    }
    return;
  }

  if (data.indexOf('hours_') === 0) {
    var hrs = parseInt(data.replace('hours_', ''), 10);
    var s = getState(chatId);
    if (s && s.scenario === 'main_hours' && !isNaN(hrs) && hrs >= 0 && hrs <= 24) {
      var dateStr = s.payload.date || getTodayMsk();
      var isWeekend = s.payload.weekend === true;
      addWorkLogEntry(dateStr, JOB_MAIN, hrs, isWeekend ? STATUS_WEEKEND_WORK : STATUS_WORK);
      clearState(chatId);
      sendTelegramMessage(chatId, 'Записано: ' + hrs + ' ч.');
    }
    return;
  }
}

function handleHelp(chatId) {
  var msg =
    'Статус — ЗП, вторая работа, остаток бюджета\n' +
    'Расход — записать расход\n' +
    'Доход — записать внезарплатный доход';
  sendTelegramMessage(chatId, msg, buildMainMenuKeyboard());
}

function handleStatus(chatId) {
  try {
    var today = getTodayMsk();
    var acc = getAccruedSummaryForPayday();
    var nextPay = getNextPayDate(today);
    var balance = getBudgetBalance();
    var startMonth = today.substring(0, 7) + '-01';
    var secondMonth = getAccruedSecondForPeriod(startMonth, today);
    logInfo('handleStatus: period=' + acc.periodStart + '-' + acc.periodEnd + ' main=' + acc.accruedMain + ' second=' + acc.accruedSecond + ' balance=' + balance);
    var msg =
      'Накоплено ЗП (основная) с последней выплаты: ' + Math.round(acc.accruedMain) + ' руб.\n' +
      'Накоплено по второй работе за месяц: ' + Math.round(secondMonth) + ' руб.\n' +
      'Остаток бюджета (доходы − расходы): ' + Math.round(balance) + ' руб.\n' +
      'Следующая выплата: ' + nextPay + '.';
    sendTelegramMessage(chatId, msg, buildInlineKeyboard([
      [{ text: 'Расход', callback_data: 'cmd_expense' }, { text: 'Доход', callback_data: 'cmd_income' }]
    ]));
  } catch (e) {
    logErrorWithException('handleStatus', e);
    sendTelegramMessage(chatId, 'Ошибка при расчёте. Проверьте данные в таблице.');
  }
}

function handleSecondJobStatus(chatId) {
  var yesterday = getYesterdayMsk();
  var orders = getOrdersForPeriod(yesterday, yesterday);
  var sum = 0;
  for (var i = 0; i < orders.length; i++) sum += orders[i].amount;
  var msg = 'За вчера (' + yesterday + '): заказов ' + orders.length + ', сумма ' + Math.round(sum) + ' руб.';
  sendTelegramMessage(chatId, msg);
}

function sendMainWorkPrompt(chatId) {
  sendTelegramMessage(chatId, 'Как прошёл рабочий день?', buildMainWorkKeyboard());
}

function sendSecondJobPrompt(chatId) {
  sendTelegramMessage(chatId, 'Доходы со второй работы за вчера?', buildSecondJobKeyboard());
}

function sendPaydayPrompt(chatId) {
  try {
    var acc = getAccruedSummaryForPayday();
    var msg =
      'Накоплено к выплате: ' + Math.round(acc.accruedTotal) + ' руб.\n' +
      '(основная: ' + Math.round(acc.accruedMain) + ', вторая: ' + Math.round(acc.accruedSecond) + ')\n\n' +
      'Сколько фактически пришло на карту? (введите число)';
    setState(chatId, 'payday_amount', '0', { accrued: { main: acc.accruedMain, second: acc.accruedSecond }, periodStart: acc.periodStart, periodEnd: acc.periodEnd });
    sendTelegramMessage(chatId, msg);
  } catch (e) {
    logErrorWithException('sendPaydayPrompt', e);
    sendTelegramMessage(chatId, 'Ошибка расчёта накоплений.');
  }
}

function sendReminderMainWork(chatId) {
  sendTelegramMessage(chatId, 'Напоминание: как прошёл рабочий день?', buildMainWorkKeyboard());
}

function sendReminderSecondJob(chatId) {
  sendTelegramMessage(chatId, 'Напоминание: доходы со второй работы за вчера?', buildSecondJobKeyboard());
}
