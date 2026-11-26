"""Idempotent official catalogue seed; never modifies farmer cycles or scientific parameters."""
from datetime import date
from sqlalchemy import select
from app.database import SessionLocal
from app.models import Crop, AgronomicProfile, CropVariety, VarietyProfile

VERIFIED_ON = date(2026, 9, 27)
IIWBR = 'https://iiwbr.org.in/technology-developed/'
ICAR_HD = 'https://icar.org.in/en/node/12081'
TIMELY = 'wheat-western-up-nwpz-irrigated-timely'
EARLY = 'wheat-western-up-nwpz-irrigated-early-high-fertility'
RESTRICTED = 'wheat-western-up-nwpz-restricted-timely'


def seed_catalogue(db):
    crop = db.scalar(select(Crop).where(Crop.crop_name == 'Wheat'))
    if crop is None:
        crop = Crop(crop_name='Wheat')
        db.add(crop); db.flush()
    source = dict(verification_status='official_verified', source_organization='ICAR-IIWBR', source_url=IIWBR,
                  source_identifier='Technology Developed: NWPZ seed production programme 2024-25', verified_on=VERIFIED_ON)
    for code, sowing, irrigation, fertility in [(TIMELY, 'timely', 'irrigated', None),
            (EARLY, 'early', 'irrigated', 'high_fertility'), (RESTRICTED, 'timely', 'restricted_irrigation', None)]:
        if db.get(AgronomicProfile, code) is None:
            db.add(AgronomicProfile(code=code, crop_id=crop.crop_id, country='India', state='Uttar Pradesh',
                region='Western Uttar Pradesh', zone_code='NWPZ', zone_name='North Western Plains Zone',
                sowing_condition=sowing, irrigation_condition=irrigation, fertility_condition=fertility,
                agricultural_timezone='Asia/Kolkata', scope_note='Western Uttar Pradesh, excluding Jhansi division. Eastern UP and other regions are outside this MVP.', **source))
    db.flush()
    names = {'DBW 370': 'Karan Vaidehi', 'DBW 371': 'Karan Vrindha', 'DBW 372': 'Karan Varuna',
             'DBW 327': 'Karan Shivani', 'DBW 332': 'Karan Aditya', 'DBW 303': 'Karan Vaishnavi',
             'DBW 187': 'Karan Vandana', 'DBW 222': 'Karan Narendra', 'DBW 296': 'Karan Aishvarya', 'HD 3226': None}
    for code, name in names.items():
        if db.get(CropVariety, code) is None:
            db.add(CropVariety(code=code, display_name=f'{code} ({name})' if name else code, crop_id=crop.crop_id))
    db.flush()
    mappings = [(EARLY, code, 2023 if code in {'DBW 370', 'DBW 371', 'DBW 372'} else 2021)
                for code in ['DBW 370', 'DBW 371', 'DBW 372', 'DBW 327', 'DBW 332', 'DBW 303', 'DBW 187']]
    mappings += [(TIMELY, 'DBW 222', 2020), (TIMELY, 'DBW 187', 2020), (TIMELY, 'HD 3226', None), (RESTRICTED, 'DBW 296', 2021)]
    for profile, variety, year in mappings:
        if db.get(VarietyProfile, (profile, variety)) is not None:
            continue
        metadata = dict(source)
        extra = {}
        if variety == 'HD 3226':
            metadata.update(source_organization='ICAR / ICAR-IARI', source_url=ICAR_HD,
                            source_identifier='Wheat Variety HD 3226: irrigated timely-sown agronomic practices')
            extra = dict(sowing_window_start='11-05', sowing_window_end='11-25', first_irrigation_about_das=21,
                         irrigation_note='Source describes first irrigation around 21 days after sowing and later irrigation according to need. Informational metadata only; not a pump schedule.')
        db.add(VarietyProfile(profile_code=profile, variety_code=variety, release_year=year, **metadata, **extra))
    db.flush()


if __name__ == '__main__':
    with SessionLocal.begin() as session:
        seed_catalogue(session)
    print('Official catalogue seeded: 3 Western-UP profiles, 10 varieties, 11 compatible mappings. Existing rows and crop cycles preserved.')
