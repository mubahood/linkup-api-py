"""
Migration 0044: seed lat/lng for every Uganda district in lu_locations.

Before this, only city-level rows (38/38) had coordinates — all 133
district-level rows had NULL lat/lng, so map-browse had no fallback position
for any member who only has a district set (the common case — GPS
verification is optional, district selection during onboarding is not).

Coordinates are each district's approximate administrative-center town —
deliberately coarse, not survey-grade: map-browse only ever shows a further
randomized/fuzzed position derived from these (see
backend/domains/sparks/service.py:_fuzzed_coords), so a few km of imprecision
here doesn't matter and actually makes triangulation even less meaningful.
"""

DISTRICT_COORDS = {
    # Central
    'Kampala': (0.3476, 32.5825), 'Wakiso': (0.4044, 32.4592),
    'Mukono': (0.3533, 32.7553), 'Mpigi': (0.2264, 32.3306),
    'Buikwe': (0.3400, 32.9500), 'Kayunga': (0.6931, 32.8917),
    'Luwero': (0.8500, 32.4750), 'Nakaseke': (0.7333, 32.2333),
    'Nakasongola': (1.3122, 32.4614), 'Mityana': (0.4031, 32.0439),
    'Mubende': (0.5836, 31.3919), 'Kiboga': (0.9167, 31.7667),
    'Kyankwanzi': (0.9333, 31.6667), 'Sembabule': (-0.0833, 31.4500),
    'Gomba': (0.2000, 31.8667), 'Butambala': (0.2000, 32.0833),
    'Kalungu': (-0.1167, 31.7667), 'Bukomansimbi': (-0.2000, 31.6167),
    'Lwengo': (-0.4000, 31.4167), 'Lyantonde': (-0.4000, 31.1500),
    'Rakai': (-0.7167, 31.5333), 'Kyotera': (-0.6167, 31.5167),
    'Buvuma': (0.3833, 33.2500), 'Kalangala': (-0.3000, 32.2333),
    'Kamuli': (0.9500, 33.1167), 'Kassanda': (0.5833, 31.9333),
    'Masaka': (-0.3333, 31.7333),
    # Eastern
    'Jinja': (0.4478, 33.2026), 'Iganga': (0.6000, 33.4667),
    'Bugiri': (0.5833, 33.7500), 'Namayingo': (-0.1667, 33.8667),
    'Busia': (0.4608, 34.0917), 'Mayuge': (0.4667, 33.4833),
    'Buyende': (1.1500, 33.1333), 'Kaliro': (0.9167, 33.5000),
    'Luuka': (0.6667, 33.3167), 'Bugweri': (0.4333, 33.6167),
    'Namutumba': (0.7500, 33.6667), 'Mbale': (1.0827, 34.1755),
    'Manafwa': (0.9167, 34.3667), 'Namisindwa': (0.9333, 34.3000),
    'Bududa': (0.9667, 34.3333), 'Bulambuli': (1.0333, 34.3667),
    'Sironko': (1.2333, 34.2500), 'Kapchorwa': (1.4000, 34.4500),
    'Kween': (1.5333, 34.5667), 'Bukwo': (1.3167, 34.7667),
    'Tororo': (0.6928, 34.1811), 'Butaleja': (0.8500, 33.9333),
    'Budaka': (1.0000, 33.9333), 'Pallisa': (1.1500, 33.7167),
    'Kibuku': (1.0500, 33.7833), 'Butebo': (1.0833, 33.9333),
    'Kumi': (1.4667, 33.9333), 'Ngora': (1.4667, 33.7667),
    'Bukedea': (1.3333, 34.0833), 'Serere': (1.5000, 33.5500),
    'Soroti': (1.7147, 33.6111), 'Katakwi': (1.9000, 33.9667),
    'Amuria': (2.0167, 33.6333), 'Kapelebyong': (2.0500, 33.9500),
    'Kaberamaido': (1.7500, 33.2167),
    # Northern (Acholi / Lango / Karamoja / West Nile)
    'Gulu': (2.7746, 32.2990), 'Amuru': (2.9833, 31.9500),
    'Nwoya': (2.6000, 31.9333), 'Omoro': (2.7167, 32.2000),
    'Kitgum': (3.2783, 32.8783), 'Lamwo': (3.6000, 32.9167),
    'Pader': (2.8333, 33.2500), 'Agago': (2.8500, 33.4667),
    'Karenga': (3.4500, 33.6500), 'Lira': (2.2350, 32.9096),
    'Alebtong': (2.2667, 33.3167), 'Otuke': (2.4000, 33.3667),
    'Dokolo': (1.9167, 33.1667), 'Kole': (2.4167, 32.7667),
    'Oyam': (2.2833, 32.3833), 'Apac': (1.9781, 32.5375),
    'Amolatar': (1.6333, 32.8167), 'Moroto': (2.5333, 34.6667),
    'Napak': (2.4833, 34.2500), 'Nakapiripirit': (1.9000, 34.6667),
    'Amudat': (1.9833, 34.9333), 'Nabilatuk': (2.1500, 34.6333),
    'Kaabong': (3.5167, 34.1500), 'Abim': (2.7000, 33.6500),
    'Kotido': (2.9833, 34.1333), 'Adjumani': (3.3776, 31.7909),
    'Moyo': (3.6500, 31.7167), 'Obongi': (3.4667, 31.5833),
    'Yumbe': (3.4667, 31.2500), 'Koboko': (3.4167, 30.9500),
    'Maracha': (3.2833, 30.9667), 'Arua': (3.0201, 30.9111),
    'Madi-Okollo': (3.0500, 31.1500), 'Zombo': (2.1500, 30.9167),
    'Nebbi': (2.4783, 31.0889), 'Pakwach': (2.4667, 31.4833),
    # Western
    'Mbarara': (-0.6072, 30.6545), 'Isingiro': (-0.8500, 30.8000),
    'Ntungamo': (-0.8833, 30.2667), 'Rwampara': (-0.7500, 30.5500),
    'Kiruhura': (-0.1833, 30.7833), 'Kazo': (-0.1167, 30.9333),
    'Ibanda': (-0.1333, 30.4833), 'Kanungu': (-0.9167, 29.7833),
    'Rukungiri': (-0.7500, 29.9333), 'Rubanda': (-1.1500, 29.8000),
    'Kabale': (-1.2500, 29.9833), 'Kisoro': (-1.2833, 29.6833),
    'Rukiga': (-1.1167, 30.0500), 'Bushenyi': (-0.5833, 30.2167),
    'Sheema': (-0.5500, 30.3667), 'Buhweju': (-0.3833, 30.3833),
    'Mitooma': (-0.6667, 30.0500), 'Rubirizi': (-0.2667, 30.1000),
    'Kasese': (0.1833, 30.0833), 'Kabarole': (0.6667, 30.2667),
    'Kamwenge': (0.3667, 30.5500), 'Kitagwenda': (0.2333, 30.5333),
    'Kyenjojo': (0.6167, 30.6167), 'Kyegegwa': (0.4833, 31.0500),
    'Ntoroko': (1.0333, 30.4833), 'Bundibugyo': (0.7167, 30.0667),
    'Hoima': (1.4356, 31.3522), 'Kikuube': (1.2167, 31.1833),
    'Kagadi': (0.9333, 30.7167), 'Kakumiro': (0.7500, 31.2833),
    'Kibaale': (0.9333, 31.0667), 'Kiryandongo': (1.9167, 32.1167),
    'Buliisa': (2.0500, 31.4000), 'Masindi': (1.6740, 31.7150),
    'Bunyangabu': (0.5000, 30.2833),
}


def up(conn):
    with conn.cursor() as cur:
        for name, (lat, lng) in DISTRICT_COORDS.items():
            cur.execute(
                "UPDATE `lu_locations` SET `latitude`=%s, `longitude`=%s "
                "WHERE `level`='district' AND `name`=%s AND `latitude` IS NULL",
                (lat, lng, name)
            )
    conn.commit()


def down(conn):
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE `lu_locations` SET `latitude`=NULL, `longitude`=NULL "
            "WHERE `level`='district'"
        )
    conn.commit()
