"""
Uganda location hierarchy seed (P-API-02).

Dedupes the duplicate 'Uganda' country rows, then seeds the 4 regions and their
districts (country → region → district via parent_id). Idempotent.

    python -m backend.seed_locations
"""
import uuid

# Region → districts (comprehensive set of Uganda's districts).
UGANDA = {
    "Central": [
        "Buikwe", "Bukomansimbi", "Butambala", "Buvuma", "Gomba", "Kalangala",
        "Kalungu", "Kampala", "Kassanda", "Kayunga", "Kiboga", "Kyankwanzi",
        "Kyotera", "Luwero", "Lwengo", "Lyantonde", "Masaka", "Mityana", "Mpigi",
        "Mubende", "Mukono", "Nakaseke", "Nakasongola", "Rakai", "Sembabule", "Wakiso",
    ],
    "Eastern": [
        "Amuria", "Budaka", "Bududa", "Bugiri", "Bugweri", "Bukedea", "Bukwo",
        "Bulambuli", "Busia", "Butaleja", "Butebo", "Buyende", "Iganga", "Jinja",
        "Kaberamaido", "Kaliro", "Kamuli", "Kapchorwa", "Kapelebyong", "Katakwi",
        "Kibuku", "Kumi", "Kween", "Luuka", "Manafwa", "Mayuge", "Mbale",
        "Namayingo", "Namisindwa", "Namutumba", "Ngora", "Pallisa", "Serere",
        "Sironko", "Soroti", "Tororo",
    ],
    "Northern": [
        "Abim", "Adjumani", "Agago", "Alebtong", "Amolatar", "Amudat", "Amuru",
        "Apac", "Arua", "Dokolo", "Gulu", "Kaabong", "Karenga", "Kitgum", "Koboko",
        "Kole", "Kotido", "Lamwo", "Lira", "Madi-Okollo", "Maracha", "Moroto",
        "Moyo", "Nabilatuk", "Nakapiripirit", "Napak", "Nebbi", "Nwoya", "Obongi",
        "Omoro", "Otuke", "Oyam", "Pader", "Pakwach", "Yumbe", "Zombo",
    ],
    "Western": [
        "Buhweju", "Buliisa", "Bundibugyo", "Bunyangabu", "Bushenyi", "Hoima",
        "Ibanda", "Isingiro", "Kabale", "Kabarole", "Kagadi", "Kakumiro", "Kamwenge",
        "Kanungu", "Kasese", "Kazo", "Kibaale", "Kikuube", "Kiruhura", "Kiryandongo",
        "Kisoro", "Kitagwenda", "Kyegegwa", "Kyenjojo", "Masindi", "Mbarara",
        "Mitooma", "Ntoroko", "Ntungamo", "Rubanda", "Rubirizi", "Rukiga",
        "Rukungiri", "Rwampara", "Sheema",
    ],
}


def run():
    from backend.app import create_app
    app = create_app()
    with app.app_context():
        from backend.models import db
        from backend.domains.reference.models import Location

        # ── 1. Canonical Uganda (dedupe) ───────────────────────────────────
        ugandas = Location.query.filter_by(level='country').filter(
            Location.name == 'Uganda'
        ).order_by(Location.id).all()
        if not ugandas:
            ug = Location(id=str(uuid.uuid4()), name='Uganda', level='country', country_code='UG')
            db.session.add(ug); db.session.flush()
            canonical = ug.id
            dupes = []
        else:
            canonical = ugandas[0].id
            dupes = [u.id for u in ugandas[1:]]
        if dupes:
            # Repoint any children of duplicate Ugandas, then delete the dupes.
            Location.query.filter(Location.parent_id.in_(dupes)).update(
                {Location.parent_id: canonical}, synchronize_session=False)
            Location.query.filter(Location.id.in_(dupes)).delete(synchronize_session=False)
        db.session.commit()

        # ── 2. Regions ─────────────────────────────────────────────────────
        region_ids = {}
        for region in UGANDA:
            r = Location.query.filter_by(name=region, level='region', parent_id=canonical).first()
            if not r:
                r = Location(id=str(uuid.uuid4()), name=region, level='region',
                             parent_id=canonical, country_code='UG')
                db.session.add(r); db.session.flush()
            region_ids[region] = r.id
        db.session.commit()

        # ── 3. Districts ───────────────────────────────────────────────────
        created = 0
        for region, districts in UGANDA.items():
            rid = region_ids[region]
            existing = {d.name for d in Location.query.filter_by(level='district', parent_id=rid).all()}
            for name in districts:
                if name in existing:
                    continue
                db.session.add(Location(id=str(uuid.uuid4()), name=name, level='district',
                                        parent_id=rid, country_code='UG'))
                created += 1
        db.session.commit()

        total_d = Location.query.filter_by(level='district').count()
        print(f'[locations] Uganda canonical={canonical[:8]} | regions={len(region_ids)} '
              f'| districts created={created} total={total_d} | dupes removed={len(dupes)}')


if __name__ == '__main__':
    run()
