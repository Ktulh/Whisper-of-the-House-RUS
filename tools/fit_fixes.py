"""One-off layout fixes: Russian strings that overflow fixed-size text boxes in the game
(found on playtest screenshots). Run again after `export.py` if translation files are regenerated."""
import json, os
from common import TRANSLATION_DIR

FIXES = {
    "Mail": {
        # handwritten alchemy notes: long words break mid-word, last note ran off the scroll
        "Mail/24": "«Цветок-бомба: мощный удар, от аромата — прилив дофамина».",
        "Mail/25": "«Горючая смесь: ходовой реагент».",
        "Mail/28": "«Настой серебролиста: мерцает лишь по ночам».",
        "Mail/75": "«Ртутный чертополох: очищает».",
        # newspaper by-line (was almost 2x the English length)
        "Mail/13": "Всезнайкин, «Вестник Шёпота»",
        "Mail/62": "Всезнайкин, «Вестник Шёпота»",
    },
    "Image": {
        # texts stored in "Sprite"-type I2 terms (missed by the first export; see SPRITE_TERMS in export.py)
        "Image/奶奶日记1": "Постучи по трубе",
        "Image/奶奶日记2": "Корма в корзине не жалей",
        "Image/奶奶日记3": "Для неумех",
        "Image/鱼人任务": "<B>Кодовое название операции: «Искусство мертво»</B>\n\nЦель: художник Мики\nЗадача: убить творческий порыв Мики\nСуть: Рыбья голова, твоя задача — в момент, когда цель не смотрит, подменить его резец нашим особым <B>«Ножом зависимости»</B>, выяснить, подсядет ли он на него, и вовремя доложить мне.",
        "Image/星球游戏": "В высоком свете над кафедрой знающего\nПод челюстями существа, живущего в стене\nВ объятиях древней зелени\nВ теснине меж исполинским камнем и мерцающей звездой\n",
        "Image/馆长给鱼人的任务": "Новое сообщение: Эльц\nРыбарон, на днях я устроил в кабинете на втором этаже музея генеральную уборку. Когда будет время, помоги, пожалуйста, расставить всё по местам — только не днём.",
        "Image/互动种下种子": "Нажмите, чтобы посадить семена.",
        "Image/栽培指南1": "Нажмите, чтобы посадить семя.",
        "Image/鱼人过场1": "Я никому не рассказывал",
        "Image/栽培指南标题": "Гид по выращиванию",
        "Image/栽培指南": "Гид по выращиванию",
    },
}

for cat, fixes in FIXES.items():
    path = os.path.join(TRANSLATION_DIR, f"{cat}.json")
    data = json.load(open(path, encoding="utf-8"))
    seen = set()
    for e in data:
        if e["key"] in fixes:
            print(f'{e["key"]}\n   - {e["ru"]}\n   + {fixes[e["key"]]}')
            e["ru"] = fixes[e["key"]]
            seen.add(e["key"])
    assert seen == set(fixes), set(fixes) - seen
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
        f.write("\n")
