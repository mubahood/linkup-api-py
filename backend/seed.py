"""
LinkUp seed data — realistic Ugandan data for all lu_* tables.
Run: source venv/bin/activate && python -m backend.seed
"""
import uuid, json, logging, bcrypt
from datetime import datetime, timedelta
from sqlalchemy import or_

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def gen_id(): return str(uuid.uuid4())
def now(): return datetime.utcnow()
def days_ago(n): return now() - timedelta(days=n)

def seed():
    from backend.app import create_app
    app = create_app()
    with app.app_context():
        _run_seed()

def _run_seed():
    from backend.models import db
    from backend.domains.identity.models import Account
    from backend.domains.profile.models import ProfessionalProfile, Education, Experience
    from backend.domains.interest.models import InterestTag, InterestProfile
    from backend.domains.links.models import Link
    from backend.domains.hubs.models import Hub, HubMembership, HubPost
    from backend.domains.chat.models import Thread, ThreadParticipant, Message
    from backend.domains.jobs.models import Job
    from backend.domains.events.models import Event
    from backend.domains.reference.models import Institution, Org, Location

    logger.info('[seed] Starting...')

    # ── Locations ──────────────────────────────────────────────────────────
    ug_id, kampala_id, mbarara_id, gulu_id, mbale_id = [gen_id() for _ in range(5)]
    for loc in [
        Location(id=ug_id, name='Uganda', level='country', country_code='UG', latitude=1.3733, longitude=32.2903),
        Location(id=kampala_id, name='Kampala', level='city', parent_id=ug_id, country_code='UG', latitude=0.3476, longitude=32.5825),
        Location(id=mbarara_id, name='Mbarara', level='city', parent_id=ug_id, country_code='UG', latitude=-0.6067, longitude=30.6545),
        Location(id=gulu_id,   name='Gulu',    level='city', parent_id=ug_id, country_code='UG', latitude=2.7748, longitude=32.2989),
        Location(id=mbale_id,  name='Mbale',   level='city', parent_id=ug_id, country_code='UG', latitude=1.0752, longitude=34.1750),
    ]:
        if not db.session.get(Location, loc.id): db.session.add(loc)
    db.session.commit()

    # ── Institutions ───────────────────────────────────────────────────────
    mak_id, mubs_id, kyam_id, ucu_id, kiu_id = [gen_id() for _ in range(5)]
    for inst in [
        Institution(id=mak_id, name='Makerere University', short_name='Mak', type='university', country='Uganda', district='Kampala', verified=True),
        Institution(id=mubs_id, name='Makerere University Business School', short_name='MUBS', type='university', country='Uganda', district='Kampala', verified=True),
        Institution(id=kyam_id, name='Kyambogo University', short_name='KYU', type='university', country='Uganda', district='Kampala', verified=True),
        Institution(id=ucu_id, name='Uganda Christian University', short_name='UCU', type='university', country='Uganda', district='Mukono', verified=True),
        Institution(id=kiu_id, name='Kampala International University', short_name='KIU', type='university', country='Uganda', district='Kampala', verified=True),
    ]:
        if not db.session.get(Institution, inst.id): db.session.add(inst)
    db.session.commit()

    # ── Orgs ───────────────────────────────────────────────────────────────
    mtn_id, stanbic_id, airtel_id, nita_id, andela_id, jumia_id = [gen_id() for _ in range(6)]
    for org in [
        Org(id=mtn_id, name='MTN Uganda', industry='Telecommunications', size_range='1000+', verified=True),
        Org(id=stanbic_id, name='Stanbic Bank Uganda', industry='Banking & Finance', size_range='1000+', verified=True),
        Org(id=airtel_id, name='Airtel Uganda', industry='Telecommunications', size_range='1000+', verified=True),
        Org(id=nita_id, name='NITA-Uganda', industry='Government', size_range='100-500', verified=True),
        Org(id=andela_id, name='Andela', industry='Technology', size_range='500-1000', verified=True),
        Org(id=jumia_id, name='Jumia Uganda', industry='E-commerce', size_range='100-500', verified=True),
    ]:
        if not db.session.get(Org, org.id): db.session.add(org)
    db.session.commit()

    # ── Interest Tags ──────────────────────────────────────────────────────
    tag_defs = [
        ('makerere-university','education_affiliation','Makerere University','Makerere'),
        ('mubs','education_affiliation','MUBS','MUBS'),
        ('kyambogo-university','education_affiliation','Kyambogo University','Kyambogo'),
        ('stem-graduates','education_affiliation','STEM Graduates',None),
        ('ugandan-alumni','education_affiliation','Ugandan Alumni Network',None),
        ('software-engineering','professional_domain','Software Engineering',None),
        ('data-science','professional_domain','Data Science & Analytics',None),
        ('finance-banking','professional_domain','Finance & Banking',None),
        ('healthcare','professional_domain','Healthcare & Medicine','Obulamu'),
        ('education-teaching','professional_domain','Education & Teaching','Okuyigiriza'),
        ('entrepreneurship','professional_domain','Entrepreneurship','Obusuubuzi'),
        ('product-management','professional_domain','Product Management',None),
        ('design-creative','professional_domain','Design & Creative','Okukoola'),
        ('agriculture-agtech','professional_domain','Agriculture & AgTech','Olulimi'),
        ('telecommunications','professional_domain','Telecommunications',None),
        ('climate-action','causes_values','Climate Action & Environment',None),
        ('youth-empowerment','causes_values','Youth Empowerment','Okukuumira abaavu'),
        ('womens-rights','causes_values',"Women's Rights & Gender Equality",None),
        ('faith-christianity','causes_values','Faith — Christianity','Obukristu'),
        ('community-development','causes_values','Community Development',None),
        ('fitness-gym','lifestyle','Fitness & Gym',None),
        ('travel-adventure','lifestyle','Travel & Adventure',None),
        ('ugandan-cuisine','lifestyle','Ugandan Cuisine & Food','Ekyokurya'),
        ('family-parenting','lifestyle','Family & Parenting','Famiri'),
        ('football-soccer','hobbies_passions','Football / Soccer','Akabumba'),
        ('music-afrobeats','hobbies_passions','Music — Afrobeats & Ugandan Music',None),
        ('reading-books','hobbies_passions','Reading & Books',None),
        ('photography','hobbies_passions','Photography',None),
        ('gaming','hobbies_passions','Gaming',None),
        ('art-crafts','hobbies_passions','Art & Crafts','Obukozi'),
        ('kampala-based','geography_mobility','Kampala Based','Kampala'),
        ('mbarara-based','geography_mobility','Mbarara Based','Mbarara'),
        ('east-africa','geography_mobility','East Africa Region','Africa ya Mashariki'),
        ('diaspora-uk','geography_mobility','Ugandan Diaspora — UK',None),
        ('open-to-relocation','geography_mobility','Open to Relocation',None),
        ('remote-work','personality_working_style','Remote Work Advocate',None),
        ('collaborative','personality_working_style','Collaborative Team Player',None),
        ('mentorship-mentor','personality_working_style','Mentor / Coach',None),
        ('startup-mindset','personality_working_style','Startup Mindset',None),
        ('structured-planner','personality_working_style','Structured Planner',None),
        ('serious-relationship','relationship_intent','Serious Relationship',None),
        ('marriage-minded','relationship_intent','Marriage-Minded',None),
        ('friendship-first','relationship_intent','Friendship First',None),
    ]

    tag_ids = {}
    for slug, dim, name_en, name_lg in tag_defs:
        t = InterestTag.query.filter_by(slug=slug).first()
        if not t:
            t = InterestTag(id=gen_id(), slug=slug, dimension=dim, display_name_en=name_en, display_name_lg=name_lg, popularity=100, is_sensitive=(dim=='relationship_intent'))
            db.session.add(t)
        tag_ids[slug] = t.id
    db.session.commit()
    logger.info(f'[seed] {len(tag_ids)} interest tags')

    # ── Accounts ───────────────────────────────────────────────────────────
    members = [
        # samuel-ocen is the primary test account and admin for audit tests
        ('samuel-ocen','+256700000001','Samuel Ocen','Software Engineer','Building scalable systems for East Africa.'),
        ('aisha-nakayima','+256700000002','Aisha Nakayima','Product Designer','UX/UI specialist passionate about inclusive design.'),
        ('brian-ssemwogerere','+256700000003','Brian Ssemwogerere','Finance Manager','10+ years in banking across Uganda.'),
        ('christine-akello','+256700000004','Christine Akello','Public Health Officer','Improving rural health outcomes in Uganda.'),
        ('david-ochieng','+256700000005','David Ochieng','Data Scientist','ML engineer working on AgTech solutions.'),
        ('esther-namutebi','+256700000006','Esther Namutebi','Entrepreneur','Founder of a sustainable fashion brand in Kampala.'),
        ('felix-mugisha','+256700000007','Felix Mugisha','Telecoms Engineer','Network infrastructure specialist at MTN Uganda.'),
        ('grace-atim','+256700000008','Grace Atim','HR Manager','People operations for fast-growing Uganda startups.'),
        ('henry-kiwanuka','+256700000009','Henry Kiwanuka','Senior Backend Developer','Python & Go engineer. Remote work enthusiast.'),
        ('irene-nalubega','+256700000010','Irene Nalubega','Marketing Manager','Brand strategy and digital marketing for SMEs.'),
        ('james-oryem','+256700000011','James Oryem','Civil Engineer','Infrastructure projects across Northern Uganda.'),
        ('kate-achieng','+256700000012','Kate Achieng','Lawyer','Commercial law and tech regulation specialist.'),
        ('lawrence-nkurunziza','+256700000013','Lawrence Nkurunziza','Investment Analyst','Private equity and venture capital in East Africa.'),
        ('mary-nakato','+256700000014','Mary Nakato','Secondary School Teacher','Mathematics educator and STEM advocate.'),
        ('noah-tumusiime','+256700000015','Noah Tumusiime','Agribusiness Consultant','Connecting smallholder farmers to markets.'),
        ('olivia-nansubuga','+256700000016','Olivia Nansubuga','Clinical Psychologist','Mental health awareness and counselling.'),
        ('peter-odeke','+256700000017','Peter Odeke','Journalist','Investigative reporter covering East African politics.'),
        ('queen-nabirye','+256700000018','Queen Nabirye','UX Researcher','Human-centred design research for digital products.'),
        ('robert-musinguzi','+256700000019','Robert Musinguzi','DevOps Engineer','Cloud infrastructure and CI/CD pipelines.'),
        ('sarah-atuhaire','+256700000020','Sarah Atuhaire','Nutritionist','Community nutrition and food security in Western Uganda.'),
    ]

    account_ids = {}
    pw_hash = bcrypt.hashpw(b'linkup2026', bcrypt.gensalt()).decode()
    for idx, (handle, phone, name, role, bio) in enumerate(members):
        a = Account.query.filter_by(phone=phone).first()
        if not a:
            a = Account(id=gen_id(), handle=handle, display_name=name, phone=phone,
                        phone_verified=True, kyc_level=1,
                        modes_enabled=json.dumps({'professional':True,'sparks':True}),
                        account_status='active',
                        is_admin=1 if idx == 0 else 0,  # first account (samuel-ocen) is admin
                        created_at=days_ago(60))
            if hasattr(a, 'password_hash'): a.password_hash = pw_hash
            db.session.add(a); db.session.flush()
            p = ProfessionalProfile(id=gen_id(), account_id=a.id, headline=role, bio=bio,
                                    seniority='mid', current_role=role, location_id=kampala_id)
            db.session.add(p)
        else:
            # Ensure first account is always admin even if already exists
            if idx == 0:
                a.is_admin = 1
                db.session.flush()
        account_ids[handle] = Account.query.filter_by(phone=phone).first().id
    db.session.commit()
    logger.info(f'[seed] {len(account_ids)} accounts')

    # ── Education ──────────────────────────────────────────────────────────
    for handle, inst_id, degree, start, end in [
        ('samuel-ocen', mak_id, 'BSc Computer Science', 2010, 2014),
        ('aisha-nakayima', mak_id, 'BA Fine Art & Industrial Design', 2012, 2016),
        ('brian-ssemwogerere', mubs_id, 'BCom Accounting', 2008, 2012),
        ('henry-kiwanuka', mak_id, 'BSc Computer Engineering', 2011, 2015),
        ('david-ochieng', mak_id, 'BSc Mathematics', 2013, 2017),
    ]:
        a_id = account_ids.get(handle)
        if a_id and not Education.query.filter_by(account_id=a_id, degree=degree).first():
            db.session.add(Education(id=gen_id(), account_id=a_id, institution_id=inst_id,
                                     degree=degree, field=degree, start_year=start, end_year=end, verified=True))
    db.session.commit()

    # ── Experience ─────────────────────────────────────────────────────────
    for handle, org_id, title, start, end in [
        ('samuel-ocen', mtn_id, 'Junior Developer', datetime(2014,8,1), datetime(2017,6,1)),
        ('samuel-ocen', andela_id, 'Software Engineer', datetime(2017,7,1), None),
        ('aisha-nakayima', andela_id, 'Product Designer', datetime(2021,1,1), None),
        ('brian-ssemwogerere', stanbic_id, 'Finance Manager', datetime(2012,6,1), None),
        ('henry-kiwanuka', andela_id, 'Senior Backend Developer', datetime(2020,1,1), None),
    ]:
        a_id = account_ids.get(handle)
        if a_id and not Experience.query.filter_by(account_id=a_id, title=title).first():
            db.session.add(Experience(id=gen_id(), account_id=a_id, org_id=org_id, title=title,
                                      start_date=start, end_date=end, is_current=(end is None), verified=True))
    db.session.commit()

    # ── Interest Profiles ──────────────────────────────────────────────────
    member_interests = {
        'samuel-ocen':['makerere-university','software-engineering','data-science','remote-work','football-soccer','kampala-based','startup-mindset'],
        'aisha-nakayima':['makerere-university','design-creative','product-management','womens-rights','photography','kampala-based','collaborative'],
        'brian-ssemwogerere':['mubs','finance-banking','entrepreneurship','faith-christianity','family-parenting','kampala-based','structured-planner'],
        'christine-akello':['makerere-university','healthcare','community-development','youth-empowerment','collaborative'],
        'david-ochieng':['makerere-university','data-science','agriculture-agtech','software-engineering','reading-books','startup-mindset'],
        'esther-namutebi':['entrepreneurship','design-creative','womens-rights','ugandan-cuisine','travel-adventure','kampala-based'],
        'felix-mugisha':['telecommunications','software-engineering','football-soccer','kampala-based','collaborative'],
        'grace-atim':['mubs','education-teaching','womens-rights','community-development','family-parenting','kampala-based'],
        'henry-kiwanuka':['makerere-university','software-engineering','data-science','remote-work','gaming','east-africa'],
        'irene-nalubega':['mubs','entrepreneurship','design-creative','photography','music-afrobeats','kampala-based'],
        'james-oryem':['community-development','climate-action','football-soccer'],
        'kate-achieng':['makerere-university','education-teaching','womens-rights','reading-books','kampala-based'],
        'lawrence-nkurunziza':['makerere-university','finance-banking','entrepreneurship','travel-adventure','east-africa'],
        'mary-nakato':['education-teaching','youth-empowerment','stem-graduates','community-development','faith-christianity'],
        'noah-tumusiime':['agriculture-agtech','entrepreneurship','community-development','climate-action'],
        'olivia-nansubuga':['healthcare','womens-rights','community-development','kampala-based','reading-books'],
        'peter-odeke':['community-development','travel-adventure','photography','east-africa'],
        'queen-nabirye':['makerere-university','design-creative','product-management','kampala-based','womens-rights'],
        'robert-musinguzi':['software-engineering','data-science','remote-work','gaming','east-africa'],
        'sarah-atuhaire':['healthcare','agriculture-agtech','community-development','womens-rights'],
    }
    for handle, slugs in member_interests.items():
        a_id = account_ids.get(handle)
        if not a_id: continue
        existing = {ip.tag_id for ip in InterestProfile.query.filter_by(account_id=a_id).all()}
        for slug in slugs:
            t_id = tag_ids.get(slug)
            if t_id and t_id not in existing:
                db.session.add(InterestProfile(id=gen_id(), account_id=a_id, tag_id=t_id,
                                               weight=1.0, mode='professional', source='explicit'))
    db.session.commit()
    logger.info('[seed] Interest profiles done')

    # ── Links ─────────────────────────────────────────────────────────────
    for r, a in [('samuel-ocen','henry-kiwanuka'),('samuel-ocen','aisha-nakayima'),('samuel-ocen','david-ochieng'),
                 ('aisha-nakayima','queen-nabirye'),('brian-ssemwogerere','lawrence-nkurunziza'),
                 ('felix-mugisha','samuel-ocen'),('grace-atim','christine-akello'),
                 ('henry-kiwanuka','robert-musinguzi'),('irene-nalubega','esther-namutebi'),('mary-nakato','grace-atim')]:
        r_id, a_id = account_ids.get(r), account_ids.get(a)
        if r_id and a_id and not Link.query.filter_by(requester_id=r_id, addressee_id=a_id).first():
            db.session.add(Link(id=gen_id(), requester_id=r_id, addressee_id=a_id,
                                status='accepted', strength_score=0.7, created_at=days_ago(30)))
    db.session.commit()
    logger.info('[seed] Links done')

    # ── Hubs ──────────────────────────────────────────────────────────────
    hub_ids = {}
    creator = account_ids['samuel-ocen']
    for slug, name, desc, htype, inst_id in [
        ('mak-alumni','Makerere University Alumni','Official alumni network for Makerere University.','alumni',mak_id),
        ('uganda-developers','Uganda Developers','Community for software developers and tech enthusiasts across Uganda.','professional',None),
        ('kampala-young-professionals','Kampala Young Professionals','Network for ambitious young professionals (22-35) in Kampala.','geographic',None),
        ('ug-fintech','Uganda Fintech & Finance',"Where Uganda's finance and fintech ecosystem meets.",'professional',None),
        ('agtech-east-africa','AgTech East Africa','Technology-driven solutions for agriculture across East Africa.','interest',None),
    ]:
        h = Hub.query.filter_by(slug=slug).first()
        if not h:
            h = Hub(id=gen_id(), slug=slug, name=name, description=desc, type=htype,
                    institution_id=inst_id, is_public=True, created_by=creator,
                    member_count=0, created_at=days_ago(90))
            db.session.add(h); db.session.flush()
        hub_ids[slug] = h.id
    db.session.commit()

    for hub_slug, handles in {
        'mak-alumni':['samuel-ocen','aisha-nakayima','brian-ssemwogerere','henry-kiwanuka','david-ochieng','grace-atim','kate-achieng'],
        'uganda-developers':['samuel-ocen','henry-kiwanuka','david-ochieng','robert-musinguzi','felix-mugisha'],
        'kampala-young-professionals':['aisha-nakayima','irene-nalubega','esther-namutebi','brian-ssemwogerere','queen-nabirye'],
        'ug-fintech':['brian-ssemwogerere','lawrence-nkurunziza','irene-nalubega'],
        'agtech-east-africa':['david-ochieng','noah-tumusiime','james-oryem','sarah-atuhaire'],
    }.items():
        h_id = hub_ids[hub_slug]
        for handle in handles:
            a_id = account_ids.get(handle)
            if a_id and not HubMembership.query.filter_by(hub_id=h_id, account_id=a_id).first():
                db.session.add(HubMembership(id=gen_id(), hub_id=h_id, account_id=a_id,
                                             role='admin' if handle==list(handles)[0] else 'member',
                                             joined_at=days_ago(80)))
        Hub.query.get(h_id).member_count = len(handles)
    db.session.commit()

    for hub_slug, handle, content in [
        ('mak-alumni','samuel-ocen','Excited to be part of the Makerere Alumni network on LinkUp!'),
        ('uganda-developers','henry-kiwanuka','Anyone using Rust for systems programming in Uganda?'),
        ('kampala-young-professionals','aisha-nakayima','Looking for UX collaborators on a new project.'),
        ('agtech-east-africa','david-ochieng','New paper on ML for crop yield prediction in Uganda. DM for the link.'),
        ('ug-fintech','brian-ssemwogerere','Thoughts on the BOU digital currency guidelines?'),
    ]:
        h_id, a_id = hub_ids[hub_slug], account_ids[handle]
        if not HubPost.query.filter_by(hub_id=h_id, account_id=a_id).first():
            db.session.add(HubPost(id=gen_id(), hub_id=h_id, account_id=a_id,
                                   content=content, like_count=0, comment_count=0, created_at=days_ago(5)))
    db.session.commit()

    # ── Hub post comments (realistic cross-member discussion) ─────────────────
    from backend.domains.hubs.models import HubPostComment
    comment_seeds = [
        ('mak-alumni',              'samuel-ocen',   'aisha-nakayima',    'So proud of this alumni network. ConnectED!'),
        ('mak-alumni',              'samuel-ocen',   'henry-kiwanuka',    'Agreed — Makerere CS community is strong.'),
        ('uganda-developers',       'henry-kiwanuka', 'samuel-ocen',      'I tried Rust for a project at Andela — highly recommend for systems work.'),
        ('uganda-developers',       'henry-kiwanuka', 'david-ochieng',    'Also worth looking at Go for simpler concurrency.'),
        ('kampala-young-professionals', 'aisha-nakayima', 'irene-nalubega', 'Happy to collaborate on UX research! Let me know.'),
        ('agtech-east-africa',      'david-ochieng',  'noah-tumusiime',   'Really excited about this. Sharing with my farmer network.'),
        ('ug-fintech',              'brian-ssemwogerere', 'lawrence-nkurunziza', 'The BOU guidelines are quite conservative compared to Rwanda.'),
    ]
    for hub_slug, post_author_handle, commenter_handle, comment_text in comment_seeds:
        h_id = hub_ids.get(hub_slug)
        poster_id = account_ids.get(post_author_handle)
        commenter_id = account_ids.get(commenter_handle)
        if not (h_id and poster_id and commenter_id):
            continue
        post = HubPost.query.filter_by(hub_id=h_id, account_id=poster_id).first()
        if post and not HubPostComment.query.filter_by(post_id=post.id, account_id=commenter_id).first():
            db.session.add(HubPostComment(
                id=gen_id(), post_id=post.id, account_id=commenter_id,
                content=comment_text, created_at=days_ago(3),
            ))
            post.comment_count = (post.comment_count or 0) + 1
    db.session.commit()
    logger.info('[seed] Hubs done')

    # ── Threads + Messages ────────────────────────────────────────────────
    for r_handle, o_handle, messages in [
        ('samuel-ocen','henry-kiwanuka',[
            ('samuel-ocen','Hey Henry! Good to connect on LinkUp. Still at Andela?'),
            ('henry-kiwanuka','Yes! Loving the remote setup. Let\'s catch up over coffee!'),
        ]),
        ('aisha-nakayima','queen-nabirye',[
            ('aisha-nakayima','Hi Queen, saw your work on the NITA project. Impressive!'),
            ('queen-nabirye','Thanks! Would love to collaborate. Reach out anytime.'),
        ]),
    ]:
        r_id, o_id = account_ids[r_handle], account_ids[o_handle]
        if not Thread.query.join(ThreadParticipant).filter(ThreadParticipant.account_id==r_id).first():
            t = Thread(id=gen_id(), type='direct', mode='professional', created_by=r_id)
            db.session.add(t); db.session.flush()
            for p in [r_id, o_id]:
                db.session.add(ThreadParticipant(id=gen_id(), thread_id=t.id, account_id=p))
            for i, (sh, body) in enumerate(messages):
                db.session.add(Message(id=gen_id(), thread_id=t.id, sender_id=account_ids[sh],
                                       body=body, type='text', status='delivered',
                                       created_at=now()-timedelta(hours=len(messages)-i)))
            t.last_message_at = now()-timedelta(minutes=5)
    db.session.commit()
    logger.info('[seed] Threads done')

    # ── Jobs ──────────────────────────────────────────────────────────────
    poster = account_ids['samuel-ocen']
    for title, org_id, desc, emp_type, seniority, loc_id, referral in [
        ('Senior Flutter Developer',andela_id,'Build mobile solutions for African markets.','full_time','senior',kampala_id,True),
        ('Data Analyst',nita_id,'Analyse government data to improve public services.','full_time','mid',kampala_id,False),
        ('Product Designer',jumia_id,'Design e-commerce experiences for East Africa.','contract','mid',kampala_id,False),
        ('Finance Officer',stanbic_id,'Retail banking financial operations and reporting.','full_time','entry',kampala_id,False),
        ('AgTech Business Analyst',None,'Bridge technology and smallholder farmers in Eastern Uganda.','full_time','mid',mbale_id,True),
        ('Telecoms Network Engineer',mtn_id,'Maintain and expand MTN Uganda 4G/5G infrastructure.','full_time','mid',kampala_id,False),
        ('Junior Frontend Developer',None,'React/TypeScript for consumer-facing web apps.','full_time','entry',kampala_id,False),
        ('Climate Programme Officer',None,'Climate resilience programmes for rural communities.','contract','mid',mbarara_id,True),
        ('Marketing Manager',airtel_id,'Lead brand campaigns for Airtel Uganda consumer products.','full_time','senior',kampala_id,False),
        ('HR Business Partner',None,'People strategy for a 200-person tech firm.','full_time','senior',kampala_id,False),
    ]:
        if not Job.query.filter_by(title=title).first():
            db.session.add(Job(id=gen_id(), org_id=org_id, posted_by=poster, title=title,
                               description=desc, location_id=loc_id,
                               employment_type=emp_type, seniority=seniority,
                               skills=json.dumps([]), is_open=True, referral_open=referral,
                               created_at=days_ago(7), expires_at=now()+timedelta(days=30)))
    db.session.commit()
    logger.info('[seed] Jobs done')

    # ── Events ────────────────────────────────────────────────────────────
    creator_id = account_ids['samuel-ocen']
    for title, desc, etype, days_offset, is_online in [
        ('Uganda Tech Summit 2026','The flagship annual gathering of the Uganda tech ecosystem.','other',14,False),
        ('Kampala Startup Weekend','Build a startup in 54 hours — pitch, build, network.','workshop',30,False),
        ('LinkUp Networking Mixer','Monthly LinkUp member mixer in Kampala.','networking',7,True),
    ]:
        if not Event.query.filter_by(title=title).first():
            start = now()+timedelta(days=days_offset)
            db.session.add(Event(id=gen_id(), created_by=creator_id, title=title,
                                 description=desc, event_type=etype, start_at=start,
                                 end_at=start+timedelta(hours=4), location_text="Kampala, Uganda",
                                 is_online=is_online, max_attendees=200, created_at=days_ago(5)))
    db.session.commit()
    logger.info('[seed] Events done')

    # ── Dating Profiles ───────────────────────────────────────────────────────
    from backend.domains.profile.models import DatingProfile
    # Columns: handle, display_name, bio, age_min, age_max, birth_year, gender, looking_for, intent, lifestyle
    dating_seeds = [
        ('samuel-ocen',    'Sam',   'Engineer by day, football fan by weekend. Exploring Kampala one coffee at a time.', 22, 34, 1997, 'male',   'female', 'serious',  {'fitness': 'active', 'family': 'open'}),
        ('aisha-nakayima', 'Aisha', 'Designer and problem solver. Love hiking, reading, and honest conversations.',      20, 32, 1999, 'female', 'male',   'serious',  {'fitness': 'moderate', 'family': 'open'}),
        ('henry-kiwanuka', 'Henry', 'Remote-first dev, loves quiet coffee spots and spontaneous road trips.',           24, 35, 1995, 'male',   'female', 'serious',  {'fitness': 'moderate', 'family': 'wants_kids'}),
        ('grace-atim',     'Grace', 'HR specialist and Sunday church-goer. Looking for depth over speed.',              22, 33, 1997, 'female', 'male',   'serious',  {'family': 'wants_kids'}),
        ('david-ochieng',  'David', 'Data nerd by week. Farmer at heart. Will cook you Ugandan dishes.',               21, 32, 1998, 'male',   'female', 'casual',   {'fitness': 'active'}),
        ('olivia-nansubuga','Olivia','Psychologist. Believes in healing, growth, and long walks.',                      24, 36, 1995, 'female', 'male',   'serious',  {'fitness': 'moderate', 'family': 'open'}),
        ('irene-nalubega', 'Irene', 'Brand strategist. Vintage fashion lover. Will out-debate you on marketing.',       22, 33, 1998, 'female', 'male',   'casual',   {}),
        ('felix-mugisha',  'Felix', 'Telecoms engineer, MTN fan, and loud football commentator.',                       23, 35, 1996, 'male',   'female', 'open',     {'fitness': 'active'}),
        ('kate-achieng',   'Kate',  'Lawyer and bookworm. Tea not coffee. Looking for substance.',                      25, 37, 1993, 'female', 'male',   'serious',  {'family': 'open'}),
        ('noah-tumusiime', 'Noah',  'AgTech consultant. Always in the village. Loves the land.',                        22, 34, 1997, 'male',   'female', 'open',     {'fitness': 'active'}),
    ]
    for handle, dname, bio, age_min, age_max, birth_year, gender, looking_for, intent, lifestyle in dating_seeds:
        a_id = account_ids.get(handle)
        if a_id:
            dp = DatingProfile.query.filter_by(account_id=a_id).first()
            if not dp:
                db.session.add(DatingProfile(
                    id=gen_id(), account_id=a_id, display_name=dname,
                    bio=bio, age_min=age_min, age_max=age_max,
                    birth_year=birth_year, gender=gender, looking_for_gender=looking_for,
                    discoverability='discoverable',
                    intent=intent, lifestyle=lifestyle,
                    prompts=[{'question': 'My ideal weekend', 'answer': f'Something outdoors with good company — {dname} style.'}],
                ))
            else:
                # Update existing with new fields if they're missing
                if not dp.birth_year:
                    dp.birth_year = birth_year
                if not dp.gender:
                    dp.gender = gender
                if not dp.looking_for_gender:
                    dp.looking_for_gender = looking_for
                if not dp.discoverability:
                    dp.discoverability = 'discoverable'
    db.session.commit()
    logger.info(f'[seed] Dating profiles done ({len(dating_seeds)} profiles)')

    # ── Spark actions for testing mutual match ─────────────────────────────────
    from backend.domains.sparks.models import Spark, Match
    from backend.domains.chat.models import Thread, ThreadParticipant
    samuel_id = account_ids.get('samuel-ocen')
    aisha_id  = account_ids.get('aisha-nakayima')
    henry_id  = account_ids.get('henry-kiwanuka')
    # samuel → aisha spark_up (and aisha → samuel reverse already seeded → match)
    if samuel_id and aisha_id and not Spark.query.filter_by(actor_id=samuel_id, target_id=aisha_id).first():
        db.session.add(Spark(id=gen_id(), actor_id=samuel_id, target_id=aisha_id, action='spark_up'))
    # henry → samuel spark_up (so audit can spark henry → creates match)
    if henry_id and samuel_id and not Spark.query.filter_by(actor_id=henry_id, target_id=samuel_id).first():
        db.session.add(Spark(id=gen_id(), actor_id=henry_id, target_id=samuel_id, action='spark_up'))
    db.session.commit()
    # aisha → samuel spark_up → mutual match
    if samuel_id and aisha_id and not Spark.query.filter_by(actor_id=aisha_id, target_id=samuel_id).first():
        s = Spark(id=gen_id(), actor_id=aisha_id, target_id=samuel_id, action='spark_up')
        db.session.add(s)
        db.session.flush()
        existing_match = Match.query.filter(
            or_(
                (Match.account_a_id == samuel_id) & (Match.account_b_id == aisha_id),
                (Match.account_a_id == aisha_id)  & (Match.account_b_id == samuel_id),
            )
        ).first()
        if not existing_match:
            s_rev = Spark.query.filter_by(actor_id=samuel_id, target_id=aisha_id).first()
            match = Match(id=gen_id(), account_a_id=samuel_id, account_b_id=aisha_id,
                          spark_a_id=s_rev.id if s_rev else None, spark_b_id=s.id)
            db.session.add(match)
            db.session.flush()
            # Auto-create sparks thread for the match
            t = Thread(id=gen_id(), type='spark', mode='dating', created_by=samuel_id,
                       last_message_at=now())
            db.session.add(t); db.session.flush()
            for pid in [samuel_id, aisha_id]:
                db.session.add(ThreadParticipant(id=gen_id(), thread_id=t.id, account_id=pid))
            match.thread_id = t.id
    db.session.commit()
    logger.info('[seed] Spark actions + match seed done')

    logger.info('[seed] ✓ Complete! Test with: +256700000001 / OTP: 123456')


if __name__ == '__main__':
    seed()
