"""
Seed integrity validator (T-API-050).

Certifies the dummy dataset so the class of corruption behind defect D-2 can
never silently return. Run after seeding:

    python -m backend.seed_validate

Exit code 0 = all CRITICAL checks pass (quality warnings allowed); 1 = a
critical violation (these would crash live endpoints).
"""
from __future__ import annotations

import sys


def validate() -> int:
    from backend.app import create_app
    app = create_app()
    with app.app_context():
        from backend.models import db
        from backend.domains.identity.models import Account
        from backend.domains.profile.models import ProfessionalProfile, DatingProfile
        from backend.domains.interest.models import InterestProfile, InterestTag
        from backend.shared.json_safe import as_obj

        accounts = Account.query.filter(Account.deleted_at.is_(None)).all()
        total = len(accounts)

        critical = {'modes_not_object': [], 'modes_empty': []}
        quality = {'no_prof_profile': 0, 'no_avatar': 0,
                   'interests_lt5': 0, 'interest_dims_lt3': 0,
                   'dating_no_photos': 0}

        # Pre-load interest dimension map.
        tag_dim = {t.id: t.dimension for t in InterestTag.query.all()}

        for a in accounts:
            # CRITICAL — modes_enabled must deserialize to a non-empty object.
            raw = a.modes_enabled
            if not isinstance(raw, (dict, str)) and raw is not None:
                critical['modes_not_object'].append(a.handle)
            modes = as_obj(raw)
            if not modes:
                critical['modes_empty'].append(a.handle)

            # QUALITY — completeness signals (not crash-causing).
            prof = ProfessionalProfile.query.filter_by(account_id=a.id).first()
            if not prof:
                quality['no_prof_profile'] += 1
            if not a.avatar:
                quality['no_avatar'] += 1

            ips = InterestProfile.query.filter_by(account_id=a.id).all()
            if len(ips) < 5:
                quality['interests_lt5'] += 1
            dims = {tag_dim.get(ip.tag_id) for ip in ips if tag_dim.get(ip.tag_id)}
            if len(dims) < 3:
                quality['interest_dims_lt3'] += 1

            if modes.get('sparks'):
                dp = DatingProfile.query.filter_by(account_id=a.id).first()
                if not dp or not (dp.photos and len(dp.photos) >= 1):
                    quality['dating_no_photos'] += 1

        # ── Report ──────────────────────────────────────────────────────────
        print(f"\nSeed validation — {total} accounts\n" + "=" * 50)
        n_critical = sum(len(v) for v in critical.values())
        print("CRITICAL:")
        for k, v in critical.items():
            flag = "✅" if not v else "❌"
            print(f"  {flag} {k}: {len(v)}" + (f"  e.g. {v[:3]}" if v else ""))
        print("QUALITY (warnings):")
        for k, v in quality.items():
            print(f"  • {k}: {v}/{total}")

        if n_critical == 0:
            print("\n✅ PASS — no critical violations.")
            return 0
        print(f"\n❌ FAIL — {n_critical} critical violation(s).")
        return 1


if __name__ == '__main__':
    sys.exit(validate())
