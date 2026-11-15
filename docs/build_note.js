const fs = require("fs");
const path = require("path");
const {
  Document, Packer, Paragraph, TextRun, ImageRun, Table, TableRow, TableCell, WidthType, AlignmentType,
  HeadingLevel, ShadingType, BorderStyle, Footer, PageNumber, PageBreak, LevelFormat,
} = require("docx");

const ROOT = path.resolve(__dirname, "..");
const dims = JSON.parse(fs.readFileSync(path.join(ROOT, "docs/img/dims.json"), "utf8"));
const FONT = "Times New Roman";
const CONTENT_W = 9638; // A4, поля по 2 см (DXA)

// ---------- допоміжне ----------
const run = (t, o = {}) => new TextRun({ text: t, font: FONT, size: 24, ...o });
const P = (t, o = {}) => new Paragraph({
  children: Array.isArray(t) ? t : [run(t)],
  spacing: { after: 120, line: 340 },
  alignment: AlignmentType.JUSTIFIED,
  indent: o.noIndent ? undefined : { firstLine: 567 },
  ...o.p,
});
const H1 = (t) => new Paragraph({ heading: HeadingLevel.HEADING_1, children: [new TextRun({ text: t, font: FONT })], pageBreakBefore: false });
const H2 = (t) => new Paragraph({ heading: HeadingLevel.HEADING_2, children: [new TextRun({ text: t, font: FONT })] });
const hl = (t) => run(t, { highlight: "yellow" });

let figN = 0, tabN = 0;
function caption(kind, text) {
  return new Paragraph({
    children: [run(text, { size: 22 })],
    alignment: AlignmentType.CENTER, spacing: { before: 60, after: 200 },
  });
}
function figure(rel, text, maxW = 600) {
  figN++;
  const [w, h] = dims[rel];
  const sc = Math.min(1, maxW / w);
  const buf = fs.readFileSync(path.join(ROOT, rel));
  return [
    new Paragraph({
      alignment: AlignmentType.CENTER, keepNext: true, spacing: { before: 120, after: 60 },
      children: [new ImageRun({ type: "png", data: buf, transformation: { width: Math.round(w * sc), height: Math.round(h * sc) },
        altText: { title: text, description: text, name: rel } })],
    }),
    caption("fig", `Рисунок ${figN} – ${text}`),
  ];
}
const figRef = () => figN; // номер останнього рисунка

// таблиці
const border = { style: BorderStyle.SINGLE, size: 4, color: "808080" };
const borders = { top: border, bottom: border, left: border, right: border };
function cell(text, w, o = {}) {
  return new TableCell({
    borders, width: { size: w, type: WidthType.DXA },
    shading: o.head ? { fill: "E8E8E8", type: ShadingType.CLEAR } : undefined,
    margins: { top: 50, bottom: 50, left: 90, right: 90 },
    children: [new Paragraph({ alignment: o.center ? AlignmentType.CENTER : AlignmentType.LEFT,
      children: [run(text, { size: 21, bold: !!o.head, font: o.mono ? "Courier New" : FONT })] })],
  });
}
function table(widths, head, rows, o = {}) {
  const sum = widths.reduce((a, b) => a + b, 0);
  return new Table({
    width: { size: sum, type: WidthType.DXA }, columnWidths: widths,
    rows: [
      new TableRow({ tableHeader: true, children: head.map((t, i) => cell(t, widths[i], { head: true, center: true })) }),
      ...rows.map((r) => new TableRow({ cantSplit: true, children: r.map((t, i) => cell(String(t), widths[i], { mono: o.monoCols && o.monoCols.includes(i), center: o.centerCols && o.centerCols.includes(i) })) })),
    ],
  });
}
function tableCaption(text) {
  tabN++;
  return new Paragraph({ children: [run(`Таблиця ${tabN} – ${text}`, { size: 22 })], keepNext: true, spacing: { before: 160, after: 80 } });
}

// блок коду: сірий фон, Courier New
function code(src) {
  const lines = src.replace(/\s+$/, "").split("\n");
  return lines.map((l, i) => new Paragraph({
    shading: { type: ShadingType.CLEAR, fill: "F0F0F0" },
    spacing: { after: 0, line: 240 },
    keepLines: true,
    border: i === 0 ? { top: { style: BorderStyle.SINGLE, size: 4, color: "C8C8C8", space: 3 } } :
      i === lines.length - 1 ? { bottom: { style: BorderStyle.SINGLE, size: 4, color: "C8C8C8", space: 3 } } : undefined,
    children: [new TextRun({ text: l === "" ? " " : l, font: "Courier New", size: 17 })],
  })).concat([new Paragraph({ spacing: { after: 120 }, children: [] })]);
}
// фрагмент з файлу: від рядка з маркером start до рядка з маркером end (не включно)
function excerpt(file, start, end) {
  const lines = fs.readFileSync(path.join(ROOT, file), "utf8").split("\n");
  const a = lines.findIndex((l) => l.includes(start));
  if (a < 0) throw new Error("немає маркера " + start + " у " + file);
  let b = end ? lines.findIndex((l, i) => i > a && l.includes(end)) : lines.length;
  if (b < 0) throw new Error("немає кінця " + end + " у " + file);
  return lines.slice(a, b).join("\n");
}
const fileHead = (name) => new Paragraph({ spacing: { before: 120, after: 60 }, keepNext: true, children: [run(name, { font: "Courier New", size: 22 })] });

// дані експерименту з CSV
const csv = fs.readFileSync(path.join(ROOT, "results/experiment.csv"), "utf8").trim().split("\n").slice(1).map((l) => l.split(",").map(Number));
const levels = [2, 3, 4, 5, 6].map((z) => {
  const ts = csv.filter((r) => r[0] === z).map((r) => r[4]);
  const mean = ts.reduce((a, b) => a + b, 0) / ts.length;
  const sd = Math.sqrt(ts.reduce((a, b) => a + (b - mean) ** 2, 0) / (ts.length - 1));
  return { z, bits: 4 * z, n: ts.length, mean, sd, min: Math.min(...ts), max: Math.max(...ts), exp: 2 ** (4 * z) };
});
const rate = csv.reduce((a, r) => a + r[3], 0) / csv.reduce((a, r) => a + r[4], 0);
const fmt = (x) => (x >= 1 ? x.toFixed(2) : x >= 0.01 ? x.toFixed(3) : x >= 0.001 ? x.toFixed(4) : x.toFixed(5)).replace(".", ",");
const ratio = (i) => (levels[i + 1].mean / levels[i].mean).toFixed(1).replace(".", ",");


const C = [];
const T = (t) => P(t);
const step = (title, time) => H2(`${title} (≈ ${time})`);
const say = (t) => P([run("Що кажу: ", { italics: true }), run(t)], { noIndent: true });
const show = (t) => P([run("Що показую: ", { italics: true }), run(t)], { noIndent: true });

C.push(
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 80 }, children: [run("ПОЯСНЮВАЛЬНА ЗАПИСКА ДО ПРАКТИЧНОГО ЗАНЯТТЯ № 1", { size: 30, bold: true })] }),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 80 }, children: [run("«Власний блокчейн з нуля»", { size: 28 })] }),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 240 }, children: [run("Арсеній ", { size: 24 }), hl("прізвище"), run(", група ПЗПІ-23-8", { size: 24 })] }),
);
C.push(P("Ця записка подається замість відео на 5–10 хвилин. Вона побудована як сценарій: по порядку описано, що запускається, що видно на екрані і що пояснюється голосом. " +
  "Усе, що показало б відео (запуск з нуля, демонстрація роботи, пояснення), наведено нижче, а скриншоти — це справжній вивід програм із проєкту. Орієнтовний час кожного блоку вказано в дужках."));

C.push(H1("1 Що за проєкт"));
C.push(step("Вступ", "1 хв"));
C.push(show("корінь проєкту, README.md і структуру каталогів."));
C.push(say("Це власний блокчейн на Python. Готові бібліотеки взято лише для SHA-256 (hashlib), підпису Ed25519 (cryptography) і HTTP (Flask, requests). " +
  "Дерево Меркла, блоки, ланцюг, мемпул, Proof of Work, коригування складності, перевірка правил і вибір ланцюга при форку написані самостійно. " +
  "Каталог chain містить ядро, node.py це вузол з HTTP API, cli.py консольний клієнт, а attacks.py, demo_fork.py, experiment.py і attack51.py це демонстрації."));
C.push(...figure("docs/img/architecture.png", "Структура модулів проєкту", 520));
C.push(T("Шари розділені навмисно. Нижній (crypto, transaction, wallet, merkle, block) нічого не знає про мережу, тому його легко тестувати. Ланцюг і мемпул працюють зі станом рахунків, а вузол лише обгортає їх в API й розсилає дані сусідам. " +
  "Приватний ключ залишається в клієнті (wallets/*.json) і на вузол не передається: транзакцію підписує cli.py, а вузол отримує вже підписану."));

C.push(H1("2 Запуск з нуля"));
C.push(step("Встановлення і тести", "1 хв"));
C.push(show("термінал у каталозі проєкту."));
C.push(...code("pip install -r requirements.txt\npython -m pytest tests -v"));
C.push(say("Потрібен Python 3.10 або новіший. Тести проходять за кілька секунд: 55 тестів, усі зелені. Вони покривають підписи, дерево Меркла, мемпул, перевірку ланцюга, складність, збереження у файл і мережеві сценарії."));
C.push(...figure("docs/img/tests.png", "Результат запуску тестів", 380));
C.push(step("Запуск трьох вузлів", "30 с"));
C.push(...code("python run_network.py"));
C.push(say("Команда запускає три вузли на портах 5001, 5002 і 5003 як окремі процеси і з'єднує їх між собою. Кожен вузол зберігає свій ланцюг у data/node_<порт>.json. " +
  "Інші команди виконуються в другому терміналі."));

C.push(H1("3 Робота з консольним клієнтом"));
C.push(step("Гаманці, транзакція, майнінг", "1,5 хв"));
C.push(...code("python cli.py wallet new alice\npython cli.py wallet new bob\npython cli.py --node http://127.0.0.1:5001 mine --wallet alice\npython cli.py --node http://127.0.0.1:5001 send --wallet alice --to bob --amount 20 --fee 2\npython cli.py --node http://127.0.0.1:5002 mempool\npython cli.py --node http://127.0.0.1:5003 mine --wallet bob\npython cli.py --node http://127.0.0.1:5001 chain\npython cli.py --node http://127.0.0.1:5003 validate"));
C.push(...figure("docs/img/cli.png", "Сеанс роботи з клієнтом", 560));
C.push(say("Спочатку Alice майнить блок на першому вузлі й отримує 50 монет винагороди. Потім вона надсилає Bob 20 монет із комісією 2. Транзакція з'являється в мемпулі другого вузла, тобто вона розіслана по мережі. " +
  "Блок із цією транзакцією майнить третій вузол, і за командою chain на першому вузлі видно, що блок дійшов до всіх. Майнер отримує 50 плюс комісію 2, тому в Bob після майнінгу 72 монети: 20 від Alice і 52 винагороди."));
C.push(T("Усі команди кроку 7 завдання є: wallet new (створити гаманець), send, mine, chain, balance, validate, peer (додати сусіда), sync. Додатково є mempool, status і network (відключити вузол від мережі)."));

C.push(H1("4 Як це працює всередині"));
C.push(step("Транзакція і підпис", "1 хв"));
C.push(say("Адреса це перші 20 байтів SHA-256 від публічного ключа. У транзакції сім полів: sender, recipient, amount, fee, nonce, pubkey і signature. Публічний ключ додано, бо з адреси його не відновити, а вузлу треба перевірити підпис. " +
  "Підписуються всі поля, крім самого підпису, у вигляді канонічного JSON з відсортованими ключами, тому підпис не можна переклеїти на іншу суму чи отримувача. " +
  "Вузол також перевіряє, що хеш ключа дорівнює адресі відправника."));
C.push(step("Мемпул", "30 с"));
C.push(say("Перед тим як прийняти транзакцію в чергу, вузол робить чотири перевірки: підпис, дублікат у черзі й ланцюгу, nonce і баланс з урахуванням тих витрат, які відправник уже зарезервував у черзі. " +
  "Якщо хоч одна не пройшла, вузол повертає причину текстом."));
C.push(step("Блок, дерево Меркла, Proof of Work", "1,5 хв"));
C.push(...figure("docs/img/blocks.png", "Зв'язок блоків", 520));
C.push(say("Заголовок блоку містить номер, час, хеш попереднього блоку, корінь Меркла, складність і nonce. Хеш блоку це SHA-256 від заголовка. Корінь Меркла я написав сам: хеші транзакцій склеюються попарно, а якщо на рівні непарна кількість, останній хеш дублюється. " +
  "Складність у бітах: хеш має починатися з потрібної кількості нульових бітів. Чотири біти це один шістнадцятковий нуль. Першою транзакцією блоку йде винагорода майнеру: 50 монет плюс комісії. " +
  "Кожні 10 блоків вузол порівнює реальний час із бажаними 10 секундами на блок і зсуває складність, але не більше ніж на 2 біти за раз."));
C.push(step("Перевірка ланцюга", "1 хв"));
C.push(say("Функція перевірки не довіряє збереженому стану, а проходить усі блоки з генезису й відтворює стан заново. Для кожного блоку вона перевіряє номер, зв'язок із попереднім, правильну складність, Proof of Work, час, корінь Меркла, " +
  "а для кожної транзакції підпис, дублікат, nonce, баланс і розмір винагороди. Ту саму функцію використовують при додаванні блоку, при завантаженні файлу й при перевірці ланцюга від сусіда. " +
  "Тому будь-яка зміна у вже доданому блоці виявляється."));

C.push(H1("5 Мережа і розгалуження"));
C.push(step("Демонстрація форку", "2 хв"));
C.push(...code("python demo_fork.py"));
C.push(say("Скрипт сам запускає три вузли. Alice і Bob майнять по блоку, усі вузли синхронні."));
C.push(...figure("docs/img/demo_1.png", "Запуск і синхронізація", 480));
C.push(say("Потім вузол C відключається від мережі. На A і B з'являється третій блок з транзакцією Alice → Carol. Тим часом C створює власну гілку, у якій на один блок більше, тож у мережі виникає форк."));
C.push(...figure("docs/img/demo_2.png", "Форк", 440));
C.push(say("Коли C повертається, A і B завантажують його ланцюг, повністю перевіряють і переходять на нього, бо в ньому більше сумарної роботи. У лозі видно реорганізацію: висота 3 → 4, відкинуто один блок, одну транзакцію повернуто в мемпул. " +
  "Ця транзакція Alice → Carol не зникла, а потрапила в наступний блок."));
C.push(...figure("docs/img/demo_3.png", "Вирішення форку", 520));
C.push(T("Окремо відповім на питання, чому за сумарною роботою, а не за довжиною: довжина не показує вкладених обчислень, бо можна нарізати багато легких блоків. Тест test_heavier_chain_wins_even_if_shorter показує, що ланцюг із 7 блоків, у якому складність зросла, перемагає ланцюг із 10 легких блоків."));

C.push(H1("6 П'ять атак"));
C.push(step("attacks.py", "3 хв"));
C.push(...code("python attacks.py"));
C.push(say("Скрипт піднімає вузол, будує невелику історію й по черзі атакує його."));
C.push(P([run("Атака 1. ", { bold: true }), run("Змінюю суму в старому блоці з 20 на 2000. Хеш блоку не змінився, але корінь Меркла в заголовку вже не відповідає транзакціям, і перевірка це ловить. Підроблений файл, покладений на диск, вузол при запуску відкидає й починає з генезису.")], { noIndent: true }));
C.push(...figure("docs/img/attack_1.png", "Атака 1", 460));
C.push(P([run("Атака 2. ", { bold: true }), run("Розумніший варіант: змінюю транзакцію, підписую знову, перераховую корінь і перемайнюю блок. Сам блок коректний, але в наступному блоці лежить хеш старого, і зв'язок розривається. Щоб виправити, треба перемайнити всі наступні блоки й випередити мережу.")], { noIndent: true }));
C.push(...figure("docs/img/attack_2.png", "Атака 2", 500));
C.push(P([run("Атака 3. ", { bold: true }), run("Підроблений підпис у трьох варіантах: ключ Alice, але підпис чужий; чесний підпис, але чужа адреса відправника; справжня транзакція Alice з підміненою сумою. Усі три відхилені як недійсний підпис.")], { noIndent: true }));
C.push(...figure("docs/img/attack_3.png", "Атака 3", 480));
C.push(P([run("Атака 4. ", { bold: true }), run("Подвійна витрата: Alice тратить майже весь баланс двічі. Друга транзакція відхилена в мемпулі, бо кошти вже зарезервовані. Нечесний майнер, який вставив обидві в один блок, отримав відхилений блок.")], { noIndent: true }));
C.push(...figure("docs/img/attack_4.png", "Атака 4", 500));
C.push(P([run("Атака 5. ", { bold: true }), run("Повтор вже підтвердженої транзакції. Вузол відхиляє її як дублікат. А якщо припустити, що списку tx_id немає, перевірка блоку все одно відхиляє повтор через nonce, бо nonce Alice уже використано.")], { noIndent: true }));
C.push(...figure("docs/img/attack_5.png", "Атака 5", 460));

C.push(H1("7 Експеримент зі складністю"));
C.push(step("experiment.py", "1 хв"));
C.push(...code("python experiment.py"));
C.push(say(`Скрипт майнить блоки для п'яти рівнів, від 2 до 6 шістнадцяткових нулів, по 10 запусків на рівень. Час росте експоненційно: кожен додатковий hex-нуль означає 4 біти, тобто в 16 разів менша ймовірність успіху за спробу. ` +
  `Мої виміри: з 4 до 5 нулів середній час зріс у ${ratio(2)} раза (${fmt(levels[2].mean)} → ${fmt(levels[3].mean)} с), з 5 до 6 нулів у ${ratio(3)} раза (${fmt(levels[3].mean)} → ${fmt(levels[4].mean)} с). ` +
  `Не рівно 16, бо час пошуку випадковий, а я усереднюю лише 10 запусків. Швидкість майнера близько ${(rate / 1e6).toFixed(2).replace(".", ",")} млн хешів за секунду.`));
C.push(...figure("results/experiment.png", "Графік експерименту (вісь часу логарифмічна)", 480));

C.push(H1("8 Додаткові завдання"));
C.push(step("Легкий клієнт і атака 51 %", "1,5 хв"));
C.push(say("Легкий клієнт (light_client.py) зберігає лише заголовки блоків і сам перевіряє їх зв'язок, Proof of Work і складність. Щоб дізнатися, чи є транзакція в блоці, він просить у вузла доказ Меркла, тобто хеші-сусіди на шляху до кореня, перераховує корінь і порівнює з заголовком."));
C.push(say("Атака 51 % (attack51.py). Спершу на справжньому коді: атакувальник платить магазину 60 монет, платіж отримує три підтвердження, а він приховано майнить довшу гілку без цього платежу. Коли в ній більше роботи, він її публікує, вузли її приймають, і баланс магазину стає 0. " +
  "Потім симуляція: при частці потужності 30 % і шести підтвердженнях імовірність успіху 8,9 %, при 45 % уже 64,8 %, а від 50 % атака вдається завжди."));
C.push(...figure("results/attack51.png", "Імовірність успіху атаки 51 %", 450));

C.push(H1("9 Відповіді на питання до захисту"));
C.push(T("Чому зміна одного байта в третьому блоці ламає наступні? Бо хеш третього блоку змінюється, і в четвертому prev_hash вказує на старий хеш; полагодження четвертого змінює його хеш і ламає п'ятий, і так до кінця."));
C.push(T("Що підписується? Усі поля транзакції, крім підпису, у канонічному JSON, тому підпис не переклеїти на іншу транзакцію."));
C.push(T("Навіщо корінь Меркла? Він фіксує весь набір транзакцій і дозволяє довести входження однієї транзакції за log2(N) хешів, не передаючи весь блок."));
C.push(T("У скільки разів зростає час з додатковим hex-нулем? У 16 разів, бо це 4 біти, а ймовірність успіху за спробу зменшується в 2⁴ разів."));
C.push(T("Чому найбільша робота, а не найдовший? Робота відображає реальні обчислення, а довжина ні."));
C.push(T("Захист від подвійної витрати й повтору: мемпул враховує резерв коштів і строгий nonce; перевірка блоку рахує баланс послідовно; повтор відхиляється як дублікат, а без списку tx_id через nonce."));
C.push(T("Що з транзакціями програного блоку? replace_chain збирає їх і повертає в мемпул після перевірки; ті, що вже недійсні (наприклад, nonce зайнятий), відкидаються."));
C.push(T("Від чого не захищена система? Від атаки 51 %, маніпуляції мітками часу, Sybil та Eclipse (вузли не автентифікуються), переповнення мемпулу, повтору в іншій мережі з тим самим генезисом (немає chain_id), гонки при 0 підтверджень, крадіжки ключа з відкритого файлу, " +
  "а дерево Меркла з дублюванням останнього листка теоретично вразливе до CVE-2012-2459."));

C.push(H1("10 Завершення"));
C.push(P("Підсумок: мережа з трьох вузлів обмінюється транзакціями й блоками, перевірка ланцюга ловить будь-яку підміну даних, усі п'ять атак відбито, експеримент підтвердив експоненційну залежність, а форк вирішується за сумарною роботою без втрати транзакцій. " +
  "Код, тести, README і звіт лежать у репозиторії (посилання у звіті). Під час роботи використовувався ШІ-асистент Claude, і я готовий пояснити кожен модуль."));

const doc = new Document({
  creator: "ПЗПІ-23-8", title: "Пояснювальна записка до ПЗ 1",
  styles: {
    default: { document: { run: { font: FONT, size: 24 } } },
    paragraphStyles: [
      { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true, run: { font: FONT, size: 28, bold: true }, paragraph: { spacing: { before: 320, after: 140 }, keepNext: true, outlineLevel: 0 } },
      { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true, run: { font: FONT, size: 25, bold: true }, paragraph: { spacing: { before: 200, after: 100 }, keepNext: true, outlineLevel: 1 } },
    ],
  },
  sections: [{
    properties: { page: { size: { width: 11906, height: 16838 }, margin: { top: 1134, bottom: 1134, left: 1134, right: 1134 } } },
    footers: { default: new Footer({ children: [new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ children: [PageNumber.CURRENT], font: FONT, size: 22 })] })] }) },
    children: C,
  }],
});
Packer.toBuffer(doc).then((b) => {
  const out = path.join(ROOT, "Записка_ПЗ1_замість_відео.docx");
  fs.writeFileSync(out, b);
  console.log("written", b.length);
});
