"""
seed_demo.py — 500 realistic Ugandan demo profiles for LinkUp.
Run: source venv/bin/activate && python -m backend.seed_demo

Fully idempotent. Safe to run multiple times.
Photos: randomuser.me (200 stable portraits) + picsum.photos (stable covers/gallery).
All profiles score 95/100 completion (Expert tier).
"""
import uuid, json, random, logging
from datetime import datetime, timedelta, date

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

random.seed(42)

_pw_hash_cache = None


def gen_id():  return str(uuid.uuid4())
def now():     return datetime.utcnow()
def dago(n):   return now() - timedelta(days=n)


def get_pw_hash():
    global _pw_hash_cache
    if not _pw_hash_cache:
        import bcrypt
        _pw_hash_cache = bcrypt.hashpw(b'111111', bcrypt.gensalt()).decode()
    return _pw_hash_cache


# ── Photo helpers ─────────────────────────────────────────────────────────────
# Verified African portraits (Unsplash) — real human faces, gender-matched.
_MEN_IDS = [
    '1518882570151-157128e78fa1', '1605980776566-0486c3ac7617',
    '1562173650-f61426fbe683', '1564541558234-ef406c118d0c',
    '1532437698276-c2ac365e7147', '1612214070782-b97cad77ca54',
    '1643904524951-2a3a58856745', '1659093728055-45f8275166d9',
    '1714118657863-2843a622718b',
]
_WOMEN_IDS = [
    '1593351799227-75df2026356b', '1613876215075-276fd62c89a4',
    '1505421031134-e57263cae630', '1619694770795-e21c58464159',
    '1604247203891-ae01b7b2f1bb', '1532076904124-d4e8fe7fbbec',
    '1548207775-a7676e36f20a', '1636302926027-9619142d7173',
    '1620424037570-15137a4a562d', '1664662566408-ef40c502a66b',
    '1628682814595-a3f0816b25ff', '1534470717-233b39a41c54',
]

def _face_url(pid):
    return (f"https://images.unsplash.com/photo-{pid}"
            "?w=640&q=72&fit=crop&crop=faces")

def avatar_url(gender, n):
    pool = _MEN_IDS if gender == 'male' else _WOMEN_IDS
    return _face_url(pool[n % len(pool)])

def cover_url(seed_str):
    return f"https://picsum.photos/seed/{seed_str}/900/300"

def gallery_url(seed_str, n):
    # Dating-gallery photos are real African portraits (deterministic per seed).
    pool = _MEN_IDS + _WOMEN_IDS
    h = (sum(ord(c) for c in str(seed_str)) + n * 7) % len(pool)
    return _face_url(pool[h])


# ── Name data ─────────────────────────────────────────────────────────────────
MALE_FIRST = [
    'Ssemujju','Kato','Mutebi','Kayiwa','Mugwanya','Musoke','Waiswa','Sentamu',
    'Lwanga','Bukenya','Kamya','Nyanzi','Mukasa','Nsubuga','Lutaya','Byarugaba',
    'Lubega','Ndawula','Kawuki','Katongole','Oryem','Okello','Odongo','Ochola',
    'Ojok','Otim','Owor','Opio','Mwesigwa','Bagyenda','Byamukama','Tumwebaze',
    'Byaruhanga','Wandera','Wangwe','Mafabi','Masaba','Odoi','Kabali','Zimbe',
    'Ssekabira','Nsereko','Kavuma','Kyeyune','Kizito','Ntambi','Muhumuza','Agaba',
    'Ampaire','Ronald','Brian','Joel','Emmanuel','Robert','Daniel','Moses',
    'Joshua','Aaron','Patrick','Francis','Samuel','Lawrence','Richard','George',
]

FEMALE_FIRST = [
    'Nalwoga','Namutebi','Nakimuli','Namubiru','Nalubega','Nakato','Namuganza',
    'Nansubuga','Nakazibwe','Achieng','Apio','Adong','Abalo','Achen','Lamunu',
    'Akello','Anena','Birungi','Kemigisha','Kemirembe','Muheirwe','Natukunda',
    'Tukahirwa','Namanya','Nankindu','Namusobya','Nakabugo','Nabaggala','Nakyama',
    'Nakyeyune','Ainembabazi','Tuhairwe','Atuhairwe','Ninsiima','Kebirungi',
    'Tusiime','Asio','Aber','Ajok','Achola','Sandra','Sharon','Gloria','Doreen',
    'Patricia','Christine','Caroline','Harriet','Agnes','Grace','Stella','Diana',
    'Judith','Rachael','Faith','Hope','Joy','Mercy','Ruth','Esther','Deborah',
    'Lydia','Priscilla','Miriam','Florence','Juliet','Irene','Vivian',
]

SURNAMES = [
    'Ssemujju','Kato','Mutebi','Kayiwa','Mugwanya','Musoke','Waiswa','Sentamu',
    'Lwanga','Bukenya','Kamya','Nyanzi','Mukasa','Nsubuga','Lutaya','Byarugaba',
    'Lubega','Ndawula','Kawuki','Katongole','Oryem','Okello','Odongo','Ochola',
    'Otim','Owor','Mwesigwa','Bagyenda','Byamukama','Tumwebaze','Byaruhanga',
    'Wandera','Mafabi','Masaba','Odoi','Kabali','Ssekabira','Nsereko','Kavuma',
    'Kyeyune','Kizito','Ntambi','Muhumuza','Agaba','Ampaire','Chebet','Barasa',
    'Wangwe','Tusiime','Rwangisa','Kikomeko','Nakaayi','Zziwa','Mubiru','Bbosa',
    'Wasswa','Ggoobi','Luyombya','Kakande','Rwabwoogo','Nimusiima','Tumusiime',
    'Twinoburyo','Kyomuhendo','Tinkasimire','Ssempijja','Nalweyiso','Nanteza',
    'Nabwire','Nabirye','Nagasha','Nakiyingi','Nakibuuka','Nakafeero','Sekimpi',
    'Matovu','Kabugo','Kalungi','Nambooze','Kabugho','Kyokwijuka','Muhwezi',
    'Tumukunde','Asiimwe','Rutagengwa','Busingye','Turyahabwe','Kahigiriza',
]

# ── Profession data ───────────────────────────────────────────────────────────
# (title, seniority, industry, bio_key)
PROFESSIONS = [
    ('Software Engineer', 'mid', 'Technology', 'tech'),
    ('Senior Software Engineer', 'senior', 'Technology', 'tech'),
    ('Frontend Developer', 'mid', 'Technology', 'tech'),
    ('Backend Developer', 'mid', 'Technology', 'tech'),
    ('Mobile Developer', 'mid', 'Technology', 'tech'),
    ('Data Scientist', 'senior', 'Technology', 'data'),
    ('Data Analyst', 'mid', 'Technology', 'data'),
    ('Machine Learning Engineer', 'senior', 'Technology', 'data'),
    ('DevOps Engineer', 'mid', 'Technology', 'tech'),
    ('Product Manager', 'senior', 'Technology', 'product'),
    ('UX/UI Designer', 'mid', 'Design', 'design'),
    ('Product Designer', 'mid', 'Design', 'design'),
    ('Cybersecurity Analyst', 'mid', 'Technology', 'tech'),
    ('Systems Administrator', 'mid', 'Technology', 'tech'),
    ('IT Officer', 'entry', 'Technology', 'tech'),
    ('Finance Manager', 'senior', 'Finance', 'finance'),
    ('Financial Analyst', 'mid', 'Finance', 'finance'),
    ('Accountant', 'mid', 'Finance', 'finance'),
    ('Audit Officer', 'mid', 'Finance', 'finance'),
    ('Investment Analyst', 'senior', 'Finance', 'finance'),
    ('Relationship Manager', 'mid', 'Banking', 'banking'),
    ('Branch Manager', 'senior', 'Banking', 'banking'),
    ('Credit Officer', 'mid', 'Banking', 'banking'),
    ('Tax Consultant', 'mid', 'Finance', 'finance'),
    ('Insurance Officer', 'mid', 'Finance', 'finance'),
    ('Medical Doctor', 'senior', 'Healthcare', 'health'),
    ('General Practitioner', 'mid', 'Healthcare', 'health'),
    ('Nurse', 'mid', 'Healthcare', 'health'),
    ('Pharmacist', 'mid', 'Healthcare', 'health'),
    ('Public Health Officer', 'mid', 'Healthcare', 'health'),
    ('Clinical Officer', 'mid', 'Healthcare', 'health'),
    ('Midwife', 'mid', 'Healthcare', 'health'),
    ('Nutritionist', 'mid', 'Healthcare', 'health'),
    ('Lab Technician', 'entry', 'Healthcare', 'health'),
    ('Biomedical Engineer', 'mid', 'Healthcare', 'tech'),
    ('Secondary School Teacher', 'mid', 'Education', 'edu'),
    ('University Lecturer', 'senior', 'Education', 'edu'),
    ('Primary School Teacher', 'entry', 'Education', 'edu'),
    ('Head Teacher', 'senior', 'Education', 'edu'),
    ('Education Officer', 'mid', 'Education', 'edu'),
    ('Agribusiness Consultant', 'mid', 'Agriculture', 'agri'),
    ('Agronomist', 'mid', 'Agriculture', 'agri'),
    ('Agricultural Officer', 'mid', 'Agriculture', 'agri'),
    ('Veterinary Officer', 'mid', 'Agriculture', 'agri'),
    ('AgTech Developer', 'mid', 'Technology', 'agri'),
    ('Advocate', 'mid', 'Law', 'law'),
    ('Senior Advocate', 'senior', 'Law', 'law'),
    ('Legal Officer', 'mid', 'Law', 'law'),
    ('Policy Analyst', 'senior', 'Government', 'policy'),
    ('Programme Officer', 'mid', 'NGO', 'ngo'),
    ('Community Development Officer', 'mid', 'NGO', 'ngo'),
    ('Project Manager', 'senior', 'NGO', 'ngo'),
    ('Civil Engineer', 'mid', 'Engineering', 'eng'),
    ('Structural Engineer', 'senior', 'Engineering', 'eng'),
    ('Electrical Engineer', 'mid', 'Engineering', 'eng'),
    ('Mechanical Engineer', 'mid', 'Engineering', 'eng'),
    ('Journalist', 'mid', 'Media', 'media'),
    ('TV Presenter', 'mid', 'Media', 'media'),
    ('Public Relations Officer', 'mid', 'Communications', 'media'),
    ('Content Creator', 'mid', 'Media', 'media'),
    ('Business Development Manager', 'senior', 'Business', 'biz'),
    ('Marketing Manager', 'senior', 'Marketing', 'marketing'),
    ('Brand Manager', 'mid', 'Marketing', 'marketing'),
    ('Entrepreneur', 'senior', 'Business', 'biz'),
    ('Human Resources Manager', 'senior', 'HR', 'hr'),
    ('HR Officer', 'mid', 'HR', 'hr'),
    ('Operations Manager', 'senior', 'Operations', 'ops'),
    ('Supply Chain Manager', 'senior', 'Logistics', 'ops'),
    ('Architect', 'mid', 'Architecture', 'arch'),
    ('Urban Planner', 'mid', 'Urban Planning', 'arch'),
    ('Environmental Scientist', 'mid', 'Environment', 'env'),
    ('Climate Change Analyst', 'mid', 'Environment', 'env'),
    ('Research Fellow', 'senior', 'Research', 'research'),
    ('Social Worker', 'mid', 'Social Services', 'ngo'),
    ('Graphic Designer', 'mid', 'Design', 'design'),
    ('Photographer', 'mid', 'Creative', 'creative'),
    ('Procurement Officer', 'mid', 'Procurement', 'ops'),
    ('Food Scientist', 'mid', 'Agriculture', 'agri'),
]

# ── Professional bios ─────────────────────────────────────────────────────────
BIO_TEMPLATES = {
    'tech': [
        "Software engineer passionate about building scalable, impactful products for East Africa. Believer in open source and local tech talent.",
        "Full-stack developer with a heart for Africa's digital transformation. I write clean code and mentor upcoming developers.",
        "Tech enthusiast from Uganda. Building the next generation of digital solutions — one commit at a time.",
        "Software professional combining technical depth with product thinking. Graduate of Makerere's CS programme.",
        "Engineer by training, problem-solver by nature. Working at the intersection of tech and real African challenges.",
        "Developer and open-source contributor. Love hackathons, coffee, and deploying to production on Fridays.",
        "Passionate about using technology to solve uniquely Ugandan problems — from fintech to agritech.",
        "Backend engineer who loves distributed systems. Building cloud-native infrastructure for African enterprises.",
        "Full-stack dev turned product person. Ship fast, learn faster. Kampala-based and globally connected.",
        "Mobile developer building apps that work beautifully offline — because Uganda's internet keeps improving.",
        "Engineering manager scaling teams and codebases across East Africa's growing tech ecosystem.",
        "Senior engineer who has shipped products used by millions of Ugandans. Now mentoring the next wave.",
    ],
    'data': [
        "Data scientist turning raw numbers into actionable insights for East African enterprises.",
        "ML engineer fascinated by the story Uganda's data tells. Building AI tools that work offline.",
        "Analyst with a passion for data-driven decisions. Working with government and NGOs to measure what matters.",
        "Quantitative analyst and statistician. Makerere Statistics grad who found home in machine learning.",
        "Data professional bridging academia and industry. Published researcher on digital financial inclusion.",
        "BI developer and data visualisation enthusiast. If it can be measured, I can chart it beautifully.",
        "Data scientist using AI to improve agricultural outcomes for smallholder farmers across Uganda.",
        "ML engineer building recommendation systems that understand East African contexts and languages.",
    ],
    'product': [
        "Product manager who loves turning fuzzy ideas into clear roadmaps and shipped features.",
        "Building digital products that solve real problems for African consumers.",
        "PM with engineering roots. Bridging what users need and what dev teams build.",
        "Product thinker and UX advocate. Crafting experiences Ugandans actually enjoy using daily.",
        "Product manager obsessed with metrics and user feedback. Shipped 3 consumer apps from zero to scale.",
    ],
    'design': [
        "UX designer committed to making digital products accessible and delightful for African users.",
        "Visual thinker and interaction designer. Believe good design is invisible.",
        "Product designer who researches deeply before drawing a single wireframe.",
        "Designer bridging beautiful aesthetics with inclusive, culture-aware user experiences.",
        "Creative director and brand strategist with a passion for Ugandan visual identity.",
        "Graphic designer turning brands into experiences. Kampala creative scene enthusiast.",
    ],
    'finance': [
        "Finance professional with deep expertise in East African capital markets and corporate finance.",
        "CPA with 8+ years helping Uganda's SMEs and corporates manage financial risk and grow sustainably.",
        "Financial analyst passionate about bridging formal finance with Uganda's informal economy.",
        "Accountant turned CFO-track professional. Numbers tell the story every leader needs to hear.",
        "Investment specialist focused on private equity opportunities across East and Central Africa.",
        "Finance manager helping organisations navigate Uganda's dynamic fiscal and regulatory landscape.",
        "Audit professional ensuring financial integrity in Uganda's growing corporate sector.",
        "Tax consultant helping businesses remain compliant while optimising their Uganda tax position.",
    ],
    'banking': [
        "Banker with a passion for financial inclusion — extending formal services to the unbanked.",
        "Relationship manager connecting Uganda's entrepreneurs with the capital they need to grow.",
        "Banking professional with expertise in SME lending, trade finance, and digital banking.",
        "Credit specialist who has assessed and structured over 500 loan facilities across Uganda.",
        "Branch manager who has grown portfolio from scratch. People person and numbers person in equal measure.",
    ],
    'health': [
        "Medical doctor dedicated to improving health outcomes in Uganda's under-resourced communities.",
        "Public health professional working at the intersection of policy, prevention, and community health.",
        "Nurse practitioner with experience across Mulago, Lacor, and community health settings in Uganda.",
        "Pharmacist and health advocate committed to rational medicine use across Uganda.",
        "Clinical officer who has worked across Northern Uganda's post-conflict health recovery zones.",
        "Public health specialist combining epidemiology with community engagement to prevent disease.",
        "Nutrition expert helping communities make evidence-based food choices across Uganda's regions.",
        "Midwife and maternal health champion reducing Uganda's maternal mortality one safe birth at a time.",
        "Biomedical engineer ensuring Uganda's health facilities have working, well-maintained equipment.",
        "Lab technician delivering diagnostic accuracy that saves lives in Uganda's referral hospitals.",
    ],
    'edu': [
        "Educator passionate about quality education as Uganda's most powerful development tool.",
        "University lecturer shaping the next generation of Uganda's professionals and change-makers.",
        "Teacher with a calling — transforming young minds in Uganda's secondary school system.",
        "Education officer working to improve curriculum delivery and teacher capacity across districts.",
        "Maths and science teacher on a mission to close Uganda's STEM skills gap one student at a time.",
        "Head teacher building a school culture of excellence, discipline, and community pride.",
    ],
    'agri': [
        "Agribusiness consultant connecting Uganda's smallholder farmers to market opportunities.",
        "Agronomist helping farmers increase yields through better practices and climate adaptation.",
        "Food systems professional working on sustainable agriculture across East Africa.",
        "Veterinary officer protecting Uganda's livestock and the livelihoods that depend on them.",
        "AgTech developer building precision farming tools adapted for Uganda's soil types and climate.",
        "Agricultural value chain specialist reducing post-harvest losses and increasing farmer incomes.",
        "Food scientist improving nutrition and food safety standards across Uganda's processing industry.",
    ],
    'law': [
        "Advocate at the Ugandan Bar with expertise in commercial law and technology regulation.",
        "Human rights lawyer committed to justice and accountability in Uganda.",
        "Legal officer specialising in land law, succession, and corporate governance in Uganda.",
        "Policy analyst at the intersection of law, governance, and East Africa's digital economy.",
        "State attorney working on complex criminal and civil litigation for Government of Uganda.",
    ],
    'policy': [
        "Policy analyst translating complex governance challenges into practical, evidence-based solutions.",
        "Development professional with deep experience in Uganda's education and health sectors.",
        "Strategic advisor helping government ministries design and implement impactful public policies.",
        "Government officer driving digital transformation across Uganda's public service institutions.",
    ],
    'ngo': [
        "Development professional with 8 years in Uganda's NGO and civil society sector.",
        "Programme officer implementing livelihoods projects for displaced communities in Northern Uganda.",
        "Community development specialist bridging donor expectations with community realities in Uganda.",
        "Project manager with INGO experience across Uganda, South Sudan, and DRC.",
        "Social worker committed to child protection and youth empowerment in Kampala's informal settlements.",
        "Programme coordinator delivering humanitarian response and resilience programming across Uganda.",
    ],
    'eng': [
        "Civil engineer working on Uganda's infrastructure transformation — roads, bridges, and clean water.",
        "Structural engineer ensuring buildings across Kampala are safe, sustainable, and beautiful.",
        "Electrical engineer bringing power to Uganda's last-mile communities through innovative solutions.",
        "Mechanical engineer supporting Uganda's growing manufacturing and processing industries.",
        "Environmental engineer designing solutions that balance Uganda's development with ecological health.",
    ],
    'media': [
        "Journalist covering East Africa's politics, economy, and social transformation.",
        "TV presenter and content creator telling Ugandan stories to a global audience.",
        "PR professional helping Uganda's organisations communicate their impact clearly and authentically.",
        "Investigative journalist holding power to account. New Vision and Monitor alum.",
        "Content creator and digital storyteller passionate about authentic African narratives.",
    ],
    'creative': [
        "Professional photographer capturing Uganda's beauty, culture, and everyday moments.",
        "Visual artist and photographer at the intersection of contemporary Ugandan art and global media.",
        "Photographer documenting East Africa's changing landscapes, communities, and celebrations.",
    ],
    'marketing': [
        "Marketing professional building Uganda's most recognisable consumer brands.",
        "Digital marketer helping Uganda's businesses grow through data-driven, creative campaigns.",
        "Brand strategist with experience across telecoms, banking, and FMCG in East Africa.",
        "Marketing manager who has led campaigns reaching millions of Ugandans across all channels.",
    ],
    'biz': [
        "Entrepreneur building a sustainable business in Uganda's rapidly growing middle class.",
        "Business development professional connecting Uganda's companies to regional and global opportunities.",
        "Founder and operator scaling a Ugandan business from startup to profitable SME.",
        "Sales leader who has built teams and territories across Uganda's diverse and dynamic market.",
        "Serial entrepreneur who has launched 3 ventures in Kampala's vibrant startup ecosystem.",
    ],
    'hr': [
        "HR professional building people-first organisations across Uganda's corporate sector.",
        "Talent acquisition specialist connecting Uganda's best professionals with the right opportunities.",
        "Human resources manager who believes culture eats strategy — especially in Kampala.",
        "HR business partner supporting leadership teams with people strategy and organisational design.",
    ],
    'ops': [
        "Operations manager streamlining supply chains for Uganda's leading FMCG and logistics companies.",
        "Logistics professional optimising last-mile delivery across East Africa's complex terrain.",
        "Procurement specialist ensuring value for money in Uganda's public and private sectors.",
    ],
    'arch': [
        "Architect shaping Kampala's evolving urban landscape with thoughtful, context-aware design.",
        "Urban planner working on Kampala's walkability, informal settlements, and heritage preservation.",
        "Interior designer bringing warmth and functionality to Uganda's leading hospitality spaces.",
    ],
    'env': [
        "Environmental scientist monitoring Uganda's forest cover, wetlands, and vital biodiversity.",
        "Climate change analyst helping Uganda's communities adapt to rapidly shifting weather patterns.",
        "Environmental consultant ensuring Uganda's development projects meet the highest ecological standards.",
    ],
    'research': [
        "Research fellow at Makerere's College of Health Sciences, publishing on infectious diseases.",
        "Social scientist studying Uganda's youth, urbanisation, and economic mobility.",
        "Research fellow combining field work with policy-relevant insights for Uganda's sustainable development.",
    ],
}

# ── Dating profile prompts ────────────────────────────────────────────────────
DATING_PROMPTS_MALE = [
    {'question': 'My ideal weekend', 'answer': 'A good game at Lugogo, then rolex at Wandegeya with close friends.'},
    {'question': 'A fact about me', 'answer': "I can name every Uganda Cranes squad from 2010. It's a gift and a burden."},
    {'question': 'I will always', 'answer': 'Start conversations with food recommendations. Kampala has too many hidden gems.'},
    {'question': 'Looking for', 'answer': 'Someone who challenges me intellectually and survives Kampala traffic gracefully.'},
    {'question': 'My happy place', 'answer': 'Lake Bunyonyi on a clear morning. Nothing else comes close.'},
    {'question': 'I go crazy for', 'answer': 'Nyama choma, deep conversations, and people with genuine ambition.'},
    {'question': 'On weekends I', 'answer': "Hike Namanve Forest or explore one of Kampala's many surprise restaurants."},
    {'question': 'The way to my heart', 'answer': 'Cook matooke. Properly. With gnuts sauce. That really is it.'},
    {'question': 'My proudest achievement', 'answer': 'Building something used by thousands of Ugandans. Numbers are just people.'},
    {'question': 'I want to travel to', 'answer': 'Rwanda for the gorillas, and the very slight infrastructure envy.'},
    {'question': 'My love language', 'answer': "Quality time, no phones. Sounds simple. It's actually rare."},
    {'question': 'Conversation starter', 'answer': 'What is the best Ugandan dish and why is it Rolex?'},
    {'question': 'I am looking for', 'answer': 'Someone rooted in Uganda but dreaming beyond it. Like me.'},
    {'question': 'Biggest green flag', 'answer': 'Has a favourite book and has actually read it recently.'},
]

DATING_PROMPTS_FEMALE = [
    {'question': 'My ideal date', 'answer': 'Botanical gardens walk, good food, real conversation. Simple things done well.'},
    {'question': 'One thing about me', 'answer': "I speak three Ugandan languages and code-switch without warning."},
    {'question': 'I go crazy for', 'answer': 'Groundnut stew, honest conversations, and someone who remembers the small details.'},
    {'question': 'Happy place', 'answer': 'Murchison Falls at sunset. Some places just reset everything.'},
    {'question': 'Looking for', 'answer': 'Someone who reads, travels, and can hold a real conversation over good coffee.'},
    {'question': 'My superpower', 'answer': "Finding the best food spots in any Ugandan town within 30 minutes of arriving."},
    {'question': 'I laugh about', 'answer': "Kampala traffic. If you can't laugh, you'll cry."},
    {'question': 'My proudest achievement', 'answer': "First in my family to graduate. Carried the whole village's hopes — and delivered."},
    {'question': 'Things I love', 'answer': "Long drives to the countryside, live music at Ndere Centre, and slow mornings."},
    {'question': 'My vibe', 'answer': "Ambitious, grounded, and still learning. The best chapter hasn't been written yet."},
    {'question': 'Non-negotiable', 'answer': 'Kindness. Without it, nothing else matters.'},
    {'question': 'Conversation starter', 'answer': 'Describe your perfect Sunday in Kampala. Mine involves chapati and a good book.'},
    {'question': 'I am looking for', 'answer': 'Depth over speed. Substance over performance.'},
    {'question': 'Green flag for me', 'answer': 'Has an actual opinion about something and can explain it without being rude.'},
]

# ── Location data ─────────────────────────────────────────────────────────────
CITIES = [
    ('Kampala',    0.3476,  32.5825, 40),
    ('Entebbe',    0.0512,  32.4637,  6),
    ('Jinja',      0.4244,  33.2041,  8),
    ('Mbarara',   -0.6067,  30.6545, 10),
    ('Gulu',       2.7748,  32.2989,  8),
    ('Mbale',      1.0752,  34.1750,  6),
    ('Fort Portal',0.6637,  30.2748,  5),
    ('Arua',       3.0208,  30.9108,  4),
    ('Masaka',    -0.3392,  31.7330,  4),
    ('Lira',       2.2499,  32.8998,  4),
    ('Soroti',     1.7131,  33.6109,  3),
    ('Kabale',    -1.2487,  29.9883,  3),
    ('Hoima',      1.4343,  31.3524,  3),
    ('Mukono',     0.3539,  32.7550,  4),
]

_CITY_NAMES   = [c[0] for c in CITIES]
_CITY_WEIGHTS = [c[3] for c in CITIES]

def _rand_city():
    return random.choices(_CITY_NAMES, weights=_CITY_WEIGHTS, k=1)[0]


# ── Extra universities ────────────────────────────────────────────────────────
EXTRA_UNIS = [
    ('Gulu University', 'GU', 'university', 'Gulu'),
    ('Mbarara University of Science and Technology', 'MUST', 'university', 'Mbarara'),
    ('Uganda Martyrs University', 'UMU', 'university', 'Mukono'),
    ('Ndejje University', 'NDU', 'university', 'Kampala'),
    ('ISBAT University', 'ISBAT', 'university', 'Kampala'),
    ('Nkumba University', 'NKU', 'university', 'Entebbe'),
    ('Busitema University', 'BST', 'university', 'Mbale'),
    ('Lira University', 'LU', 'university', 'Lira'),
    ('Mountains of the Moon University', 'MMU', 'university', 'Fort Portal'),
    ('Cavendish University Uganda', 'CUU', 'university', 'Kampala'),
    ('Uganda Management Institute', 'UMI', 'college', 'Kampala'),
]

# ── Extra organisations ───────────────────────────────────────────────────────
EXTRA_ORGS = [
    ('dfcu Bank Uganda', 'Banking & Finance'),
    ('Equity Bank Uganda', 'Banking & Finance'),
    ('Centenary Bank', 'Banking & Finance'),
    ('Housing Finance Bank', 'Banking & Finance'),
    ('Bank of Uganda', 'Government'),
    ('Uganda Revenue Authority', 'Government'),
    ('NSSF Uganda', 'Government'),
    ('National Water and Sewerage Corporation', 'Government'),
    ('UMEME Limited', 'Utilities'),
    ('Uganda National Roads Authority', 'Government'),
    ('KCCA', 'Government'),
    ('Ministry of Health Uganda', 'Government'),
    ('Mulago National Referral Hospital', 'Healthcare'),
    ('Infectious Diseases Institute', 'Healthcare'),
    ('Cipla Quality Chemical', 'Healthcare'),
    ('Makerere University', 'Education'),
    ('Kyambogo University', 'Education'),
    ('Vision Group', 'Media'),
    ('Monitor Publications', 'Media'),
    ('NBS TV Uganda', 'Media'),
    ('Roofings Uganda', 'Manufacturing'),
    ('Bidco Uganda', 'Manufacturing'),
    ('Crown Beverages Uganda', 'Manufacturing'),
    ('Hima Cement', 'Manufacturing'),
    ('Uganda Airlines', 'Transport'),
    ('SafeBoda', 'Technology'),
    ('Zembo Electric', 'Technology'),
    ('Flutterwave Uganda', 'Technology'),
    ('Interswitch Uganda', 'Technology'),
    ('mPharma Uganda', 'Healthcare Technology'),
    ('Liquid Intelligent Technologies', 'Technology'),
    ('Raxio Data Centre', 'Technology'),
    ('ATC Uganda', 'Telecommunications'),
    ('Roke Telkom', 'Telecommunications'),
    ('Uganda Telecom', 'Telecommunications'),
    ('BRAC Uganda', 'NGO'),
    ('World Vision Uganda', 'NGO'),
    ('ActionAid Uganda', 'NGO'),
    ('Save the Children Uganda', 'NGO'),
    ('Plan International Uganda', 'NGO'),
    ('CARE International Uganda', 'NGO'),
    ('Mercy Corps Uganda', 'NGO'),
    ('IRC Uganda', 'NGO'),
    ('UNHCR Uganda', 'UN Agency'),
    ('UNICEF Uganda', 'UN Agency'),
    ('WFP Uganda', 'UN Agency'),
    ('WHO Uganda', 'UN Agency'),
    ('GIZ Uganda', 'International Development'),
    ('USAID Uganda Mission', 'International Development'),
    ('DHL Uganda', 'Logistics'),
    ('Bollore Logistics Uganda', 'Logistics'),
    ('Crown Paints Uganda', 'Manufacturing'),
    ('Mukwano Group', 'Manufacturing'),
    ('Ruparelia Group', 'Real Estate'),
    ('Serena Hotels Uganda', 'Hospitality'),
    ('Pearl Engineering', 'Engineering'),
    ('National Environment Management Authority', 'Government'),
    ('Uganda Export Promotions Board', 'Government'),
    ('Uganda Investment Authority', 'Government'),
    ('Stanbic Bank Uganda', 'Banking & Finance'),
    ('Airtel Uganda', 'Telecommunications'),
    ('MTN Uganda', 'Telecommunications'),
    ('Andela', 'Technology'),
    ('Jumia Uganda', 'E-commerce'),
    ('NITA-Uganda', 'Government'),
]

# ── Degrees by bio-key ────────────────────────────────────────────────────────
DEGREES = {
    'tech':    ['BSc Computer Science', 'BSc Information Technology', 'BSc Software Engineering', 'BSc Computer Engineering'],
    'data':    ['BSc Statistics', 'BSc Mathematics', 'BSc Computer Science', 'MSc Data Science'],
    'product': ['BSc Computer Science', 'BBA', 'BSc Information Systems'],
    'design':  ['BA Fine Art & Industrial Design', 'BSc Architecture', 'BA Graphic Design'],
    'finance': ['BCom Accounting', 'BSc Economics', 'BBA Finance', 'BCom Finance'],
    'banking': ['BBA Banking & Finance', 'BCom Accounting', 'BSc Economics'],
    'health':  ['MBChB', 'BSc Nursing', 'Bachelor of Pharmacy', 'BSc Public Health', 'BSc Nutrition & Dietetics'],
    'edu':     ['BEd Arts', 'BEd Science', 'BA Education', 'BSc Education'],
    'agri':    ['BSc Agriculture', 'BSc Agribusiness', 'BSc Food Science & Technology'],
    'law':     ['LLB', 'LLM', 'BA Social Sciences'],
    'policy':  ['BA Social Sciences', 'MA Development Studies', 'MBA'],
    'ngo':     ['BA Social Work & Social Administration', 'BSc Public Health', 'BA Development Studies'],
    'eng':     ['BSc Civil Engineering', 'BSc Electrical Engineering', 'BSc Mechanical Engineering'],
    'media':   ['BA Mass Communication', 'BA Journalism', 'BA Public Relations'],
    'creative':['BA Fine Art', 'BA Photography', 'BSc Architecture'],
    'marketing':['BBA Marketing', 'BA Mass Communication', 'BSc Business Administration'],
    'biz':     ['BBA', 'BSc Business Administration', 'MBA', 'BCom'],
    'hr':      ['BSc Human Resource Management', 'BBA HR'],
    'ops':     ['BSc Logistics & Supply Chain', 'BBA Operations Management'],
    'arch':    ['BSc Architecture', 'BSc Urban Planning'],
    'env':     ['BSc Environmental Science', 'BSc Geography', 'MSc Environmental Management'],
    'research':['MSc Public Health', 'MA Social Sciences', 'MBChB'],
}

CERTS_POOL = [
    ('Google Project Management Certificate', 'Google', 2022),
    ('AWS Certified Solutions Architect', 'Amazon Web Services', 2023),
    ('Certified Public Accountant (CPA)', 'ICPAU Uganda', 2021),
    ('Project Management Professional (PMP)', 'PMI', 2022),
    ('Chartered Financial Analyst (CFA) Level I', 'CFA Institute', 2023),
    ('Google Data Analytics Certificate', 'Google', 2022),
    ('Certified Ethical Hacker (CEH)', 'EC-Council', 2023),
    ('ACCA Affiliate', 'ACCA', 2023),
    ('PRINCE2 Foundation', 'Axelos', 2022),
    ('Cisco Certified Network Associate (CCNA)', 'Cisco', 2021),
    ('CompTIA Security+', 'CompTIA', 2022),
    ('Scrum Master Certification (CSM)', 'Scrum Alliance', 2023),
    ('Certificate in Monitoring & Evaluation', 'MEASURE Evaluation', 2021),
    ('Lean Six Sigma Green Belt', 'IASSC', 2021),
    ('Digital Marketing Certificate', 'Google', 2022),
    ('WHO Emergency Response Training', 'WHO', 2020),
    ('USAID Partner Training Certificate', 'USAID', 2021),
    ('Human Resources Professional (HRP)', 'HRPA Uganda', 2021),
]

# ── Interests by bio-key ──────────────────────────────────────────────────────
INTERESTS_BY_KEY = {
    'tech':     ['software-engineering', 'data-science', 'product-management', 'remote-work', 'startup-mindset'],
    'data':     ['data-science', 'software-engineering', 'agriculture-agtech', 'startup-mindset', 'reading-books'],
    'product':  ['product-management', 'design-creative', 'software-engineering', 'startup-mindset'],
    'design':   ['design-creative', 'product-management', 'photography', 'art-crafts'],
    'finance':  ['finance-banking', 'entrepreneurship', 'reading-books', 'structured-planner'],
    'banking':  ['finance-banking', 'entrepreneurship', 'structured-planner', 'family-parenting'],
    'health':   ['healthcare', 'community-development', 'youth-empowerment', 'fitness-gym'],
    'edu':      ['education-teaching', 'youth-empowerment', 'community-development', 'reading-books'],
    'agri':     ['agriculture-agtech', 'entrepreneurship', 'community-development', 'climate-action'],
    'law':      ['education-teaching', 'womens-rights', 'reading-books', 'collaborative'],
    'policy':   ['community-development', 'youth-empowerment', 'east-africa', 'reading-books'],
    'ngo':      ['community-development', 'youth-empowerment', 'womens-rights', 'climate-action'],
    'eng':      ['software-engineering', 'climate-action', 'community-development', 'collaborative'],
    'media':    ['photography', 'travel-adventure', 'community-development', 'music-afrobeats'],
    'creative': ['photography', 'art-crafts', 'design-creative', 'travel-adventure'],
    'marketing':['design-creative', 'entrepreneurship', 'music-afrobeats', 'travel-adventure'],
    'biz':      ['entrepreneurship', 'finance-banking', 'startup-mindset', 'east-africa'],
    'hr':       ['community-development', 'womens-rights', 'education-teaching', 'collaborative'],
    'ops':      ['entrepreneurship', 'east-africa', 'structured-planner', 'collaborative'],
    'arch':     ['design-creative', 'art-crafts', 'travel-adventure', 'climate-action'],
    'env':      ['climate-action', 'agriculture-agtech', 'community-development', 'east-africa'],
    'research': ['data-science', 'healthcare', 'reading-books', 'makerere-university'],
}

EXTRA_TAGS = [
    'football-soccer', 'music-afrobeats', 'reading-books', 'photography', 'gaming',
    'art-crafts', 'travel-adventure', 'ugandan-cuisine', 'family-parenting', 'fitness-gym',
    'faith-christianity', 'mbarara-based', 'kampala-based', 'stem-graduates',
    'mentorship-mentor', 'remote-work', 'collaborative', 'makerere-university', 'mubs',
]

EXP_DESCRIPTIONS = [
    "Led cross-functional initiatives delivering measurable impact across the team.",
    "Managed complex projects across multiple stakeholders, meeting all key deliverables.",
    "Developed and implemented strategies that improved operational efficiency by 30%.",
    "Collaborated with regional teams to scale programmes across East Africa.",
    "Built and mentored a team of professionals, fostering a high-performance culture.",
    "Drove business development resulting in significant revenue growth for the organisation.",
    "Delivered technical solutions that improved service delivery for thousands of users.",
    "Implemented best practices that reduced costs while maintaining quality standards.",
    "Partnered with leadership to align people strategy with organisational objectives.",
    "Conducted research that informed evidence-based decision making at national level.",
]


# ─────────────────────────────────────────────────────────────────────────────
def seed():
    from backend.app import create_app
    app = create_app()
    with app.app_context():
        _run_seed()


def _run_seed():
    from backend.models import db
    from backend.domains.identity.models import Account
    from backend.domains.profile.models import (
        ProfessionalProfile, DatingProfile, Education, Experience, Certification
    )
    from backend.domains.interest.models import InterestTag, InterestProfile
    from backend.domains.reference.models import Institution, Org, Location
    from backend.domains.links.models import Link
    from backend.domains.sparks.models import Spark

    logger.info('[demo-seed] Starting 500-profile seed ...')

    # ── Ensure Uganda country location exists ─────────────────────────────────
    ug = Location.query.filter_by(name='Uganda', level='country').first()
    if not ug:
        ug = Location(
            id=gen_id(), name='Uganda', level='country',
            country_code='UG', latitude=1.3733, longitude=32.2903,
        )
        db.session.add(ug); db.session.commit()

    # ── City locations ────────────────────────────────────────────────────────
    loc_map = {}
    for cname, lat, lng, _ in CITIES:
        loc = Location.query.filter_by(name=cname, level='city').first()
        if not loc:
            loc = Location(
                id=gen_id(), name=cname, level='city', parent_id=ug.id,
                country_code='UG', latitude=lat, longitude=lng,
            )
            db.session.add(loc)
    db.session.commit()
    for cname, *_ in CITIES:
        loc = Location.query.filter_by(name=cname, level='city').first()
        if loc: loc_map[cname] = loc.id

    # ── Extra institutions ────────────────────────────────────────────────────
    inst_map = {}
    for short in ['Mak', 'MUBS', 'KYU', 'UCU', 'KIU']:
        i = Institution.query.filter_by(short_name=short).first()
        if i: inst_map[short] = i.id

    for iname, short, itype, city in EXTRA_UNIS:
        inst = Institution.query.filter_by(short_name=short).first()
        if not inst:
            inst = Institution(
                id=gen_id(), name=iname, short_name=short, type=itype,
                country='Uganda', district=city, verified=True,
            )
            db.session.add(inst)
    db.session.commit()
    for _, short, _, _ in EXTRA_UNIS:
        i = Institution.query.filter_by(short_name=short).first()
        if i: inst_map[short] = i.id

    all_inst_ids = [v for v in inst_map.values() if v]
    # Weighted pick — Makerere and MUBS more common
    heavy_shorts = ['Mak', 'MUBS', 'KYU', 'UCU', 'KIU']
    heavy_ids    = [inst_map[s] for s in heavy_shorts if inst_map.get(s)]

    def rand_inst():
        pool = heavy_ids * 3 + all_inst_ids
        return random.choice([x for x in pool if x])

    # ── Extra organisations ───────────────────────────────────────────────────
    org_map = {}
    for oname, oindustry in EXTRA_ORGS:
        o = Org.query.filter_by(name=oname).first()
        if not o:
            o = Org(
                id=gen_id(), name=oname, industry=oindustry,
                size_range='100-500', verified=True,
            )
            db.session.add(o)
    db.session.commit()
    for oname, _ in EXTRA_ORGS:
        o = Org.query.filter_by(name=oname).first()
        if o: org_map[oname] = o.id
    all_org_ids   = [v for v in org_map.values() if v]
    all_org_names = [k for k, v in org_map.items() if v]

    # ── Interest tag map ──────────────────────────────────────────────────────
    tag_map = {t.slug: t.id for t in InterestTag.query.all()}

    # ── Password hash (cached) ────────────────────────────────────────────────
    pw_hash = get_pw_hash()

    # ═════════════════════════════════════════════════════════════════════════
    # Main 500-profile generation loop
    # ═════════════════════════════════════════════════════════════════════════
    created, skipped = 0, 0
    all_demo_ids = []

    # Ugandan districts (with parent region) for dating-profile location.
    _DISTRICTS = Location.query.filter(Location.level == 'district').all()

    for i in range(500):
        gender     = 'male' if i < 250 else 'female'
        fn_list    = MALE_FIRST if gender == 'male' else FEMALE_FIRST
        first      = fn_list[i % len(fn_list)]
        last       = SURNAMES[(i * 7 + 13) % len(SURNAMES)]
        dname      = f"{first} {last}"
        handle     = f"d{i + 100}-{first.lower()}-{last.lower()}"
        phone      = f"+256700{i + 100:06d}"
        email      = f"{first.lower()}{i + 100}@linkup.ug"
        city       = _rand_city()
        loc_id     = loc_map.get(city)

        # Skip if already seeded
        existing = Account.query.filter_by(phone=phone).first()
        if existing:
            all_demo_ids.append(existing.id)
            skipped += 1
            continue

        prof_tuple  = PROFESSIONS[i % len(PROFESSIONS)]
        prof_title, seniority, industry, bio_key = prof_tuple
        bio_list    = BIO_TEMPLATES.get(bio_key, BIO_TEMPLATES['tech'])
        bio         = bio_list[i % len(bio_list)]
        photo_n     = i % 100
        av          = avatar_url(gender, photo_n)
        cv          = cover_url(f"ug-{handle}")

        # ── Account ──────────────────────────────────────────────────────────
        acc = Account(
            id=gen_id(), handle=handle, display_name=dname,
            phone=phone, email=email,
            phone_verified=True, email_verified=True,
            kyc_level=random.choice([1, 1, 1, 2]),
            modes_enabled={'professional': True, 'sparks': True},
            account_status='active',
            avatar=av, cover_photo=cv,
            location_id=loc_id,
            reputation_score=round(random.uniform(2.5, 5.0), 2),
            created_at=dago(random.randint(10, 400)),
        )
        if hasattr(acc, 'password_hash'):
            acc.password_hash = pw_hash
        db.session.add(acc)
        db.session.flush()

        # ── Professional profile ──────────────────────────────────────────────
        grad_yr    = random.randint(2005, 2022)
        short_uni  = random.choice(heavy_shorts)
        headline   = f"{prof_title} · {short_uni} '{str(grad_yr)[2:]}"
        open_to    = []
        if random.random() > 0.4: open_to.append('new_roles')
        if random.random() > 0.6: open_to.append('mentorship')
        if random.random() > 0.5: open_to.append('collaborations')

        db.session.add(ProfessionalProfile(
            id=gen_id(), account_id=acc.id,
            headline=headline, bio=bio,
            seniority=seniority, current_role=prof_title,
            location_id=loc_id, visibility_mode='public', open_to=open_to,
        ))

        # ── Education ─────────────────────────────────────────────────────────
        inst_id    = rand_inst()
        deg_list   = DEGREES.get(bio_key, DEGREES['tech'])
        degree     = deg_list[i % len(deg_list)]
        start_yr   = grad_yr - random.choice([3, 4, 5])
        db.session.add(Education(
            id=gen_id(), account_id=acc.id, institution_id=inst_id,
            degree=degree, field=degree,
            start_year=start_yr, end_year=grad_yr, verified=True,
        ))
        # 40% chance second qualification
        if random.random() > 0.6:
            pg_degs   = ['MBA', 'MSc Management', 'MSc Data Science', 'LLM', 'MEd',
                         'MSc Public Health', 'PGDM', 'MA Development Studies']
            pg_deg    = random.choice(pg_degs)
            pg_start  = grad_yr + random.randint(1, 5)
            pg_end    = pg_start + random.choice([1, 2])
            db.session.add(Education(
                id=gen_id(), account_id=acc.id, institution_id=rand_inst(),
                degree=pg_deg, field=pg_deg,
                start_year=pg_start, end_year=pg_end,
                verified=random.random() > 0.5,
            ))

        # ── Experience ────────────────────────────────────────────────────────
        n_exp      = random.choice([1, 1, 2, 2, 3])
        yrs_back   = random.randint(1, 12)
        same_titles = [t for t, _, _, bk in PROFESSIONS if bk == bio_key]

        for e_idx in range(n_exp):
            oname      = random.choice(all_org_names)
            oid        = org_map.get(oname)
            s_date     = dago(yrs_back * 365).date()
            e_date     = None if e_idx == 0 else dago((yrs_back - random.randint(1, 3)) * 365).date()
            exp_title  = prof_title if e_idx == 0 else (random.choice(same_titles) if same_titles else prof_title)
            yrs_back  += random.randint(2, 5)
            db.session.add(Experience(
                id=gen_id(), account_id=acc.id,
                org_id=oid, org_name=oname, title=exp_title,
                description=random.choice(EXP_DESCRIPTIONS),
                start_date=s_date, end_date=e_date,
                is_current=(e_idx == 0), verified=random.random() > 0.4,
            ))

        # ── Certification (50% chance) ─────────────────────────────────────────
        if random.random() > 0.5:
            cname, cissuer, cyr = random.choice(CERTS_POOL)
            issued  = date(cyr, random.randint(1, 12), 1)
            expires = date(cyr + 3, random.randint(1, 12), 1)
            db.session.add(Certification(
                id=gen_id(), account_id=acc.id,
                name=cname, issuer=cissuer,
                issued_at=issued, expires_at=expires,
                credential_url=f"https://credentials.linkup.ug/{handle}-cert",
            ))

        # ── Interests (5–8 tags) ──────────────────────────────────────────────
        base_slugs  = list(INTERESTS_BY_KEY.get(bio_key, ['software-engineering', 'kampala-based']))
        extra_pool  = [s for s in EXTRA_TAGS if s not in base_slugs]
        extra_slugs = random.sample(extra_pool, k=min(3, len(extra_pool)))
        all_slugs   = list(set(base_slugs + extra_slugs))
        random.shuffle(all_slugs)
        chosen      = all_slugs[:random.randint(5, 8)]

        for slug in chosen:
            tid = tag_map.get(slug)
            if tid:
                db.session.add(InterestProfile(
                    id=gen_id(), account_id=acc.id, tag_id=tid,
                    weight=round(random.uniform(0.5, 1.0), 2),
                    mode='professional', source='explicit',
                ))

        # ── Dating profile ────────────────────────────────────────────────────
        birth_yr     = random.randint(1982, 2003)
        age_rng      = random.choice([(18, 30), (20, 32), (22, 34), (24, 36), (25, 40)])
        intent       = random.choice(['serious', 'serious', 'open', 'casual'])
        looking_for  = 'female' if gender == 'male' else 'male'
        if random.random() > 0.93: looking_for = 'any'

        d_prompts_pool = DATING_PROMPTS_MALE if gender == 'male' else DATING_PROMPTS_FEMALE
        d_prompts      = random.sample(d_prompts_pool, k=min(3, len(d_prompts_pool)))
        # Real African portraits, gender-matched.
        _pool = _MEN_IDS if gender == 'male' else _WOMEN_IDS
        _pics = random.sample(_pool, k=min(4, len(_pool)))
        photos = [{'type': 'photo', 'url': _face_url(p)} for p in _pics]
        all_prompts = [{'type': 'photo', 'url': _face_url(p)} for p in _pics[:3]] + d_prompts

        lifestyle = {}
        if random.random() > 0.4: lifestyle['fitness'] = random.choice(['active', 'moderate', 'occasional'])
        if random.random() > 0.5: lifestyle['family']  = random.choice(['wants_kids', 'open', 'no_kids'])
        if random.random() > 0.6: lifestyle['faith']   = random.choice(['christian', 'muslim', 'no_preference'])

        dating_bio = (
            f"{bio[:90].rstrip('.')}. "
            f"{'Looking to build something real.' if gender == 'male' else 'Here for genuine connections.'}"
        )

        # 360° profiling — Uganda-weighted catalog tokens.
        _district = random.choice(_DISTRICTS) if _DISTRICTS else None
        db.session.add(DatingProfile(
            id=gen_id(), account_id=acc.id,
            display_name=first, bio=dating_bio,
            birth_year=birth_yr,
            age_min=age_rng[0], age_max=age_rng[1],
            gender=gender, looking_for_gender=looking_for,
            discoverability='discoverable',
            intent=intent, lifestyle=lifestyle, prompts=all_prompts,
            photos=photos,
            country_code='UG',
            region_id=(_district.parent_id if _district else None),
            district_id=(_district.id if _district else None),
            height_cm=(random.randint(168, 193) if gender == 'male'
                       else random.randint(150, 178)),
            sexual_orientation=random.choice(['straight'] * 9 + ['bisexual', 'gay', 'lesbian']),
            relationship_goal=random.choice(['long_term'] * 4 + ['marriage'] * 3
                + ['short_term', 'friendship', 'figuring_out']),
            smoking=random.choice(['no'] * 6 + ['social', 'social', 'yes', 'quitting']),
            drinking=random.choice(['no'] * 4 + ['social'] * 4 + ['yes', 'yes', 'sober']),
            marijuana=random.choice(['never'] * 7 + ['sometimes', 'sometimes', 'prefer_not']),
            diet=random.choice(['omnivore'] * 6 + ['no_pork', 'no_pork', 'halal', 'halal', 'vegetarian']),
            exercise=random.choice(['daily', 'often', 'often', 'sometimes', 'sometimes', 'rarely']),
            pets=random.choice(['none', 'none', 'dog', 'cat', 'both', 'want']),
            religion=random.choice(['catholic'] * 4 + ['anglican'] * 4 + ['pentecostal'] * 4
                + ['muslim'] * 3 + ['sda', 'orthodox', 'traditional', 'spiritual', 'agnostic']),
            religiosity=random.choice(['very'] * 3 + ['somewhat'] * 4 + ['not_really']),
            politics=random.choice(['none', 'none', 'nrm', 'nup', 'fdc', 'dp', 'independent', 'prefer_not']),
            education_level=random.choice(['secondary', 'certificate', 'diploma', 'diploma',
                'bachelors', 'bachelors', 'bachelors', 'masters', 'vocational']),
            industry=random.choice(['technology', 'finance', 'healthcare', 'education',
                'agriculture', 'engineering', 'legal', 'media', 'government', 'ngo',
                'business', 'sales_marketing', 'hospitality', 'transport', 'arts', 'student']),
            body_type=random.choice(['slim', 'athletic', 'athletic', 'average', 'average', 'curvy', 'plus_size']),
            zodiac=random.choice(['aries', 'taurus', 'gemini', 'cancer', 'leo', 'virgo',
                'libra', 'scorpio', 'sagittarius', 'capricorn', 'aquarius', 'pisces']),
            communication_style=random.choice(['big_texter', 'phone_caller', 'video_chat', 'in_person', 'slow_texter']),
            has_children=random.choice(['no'] * 6 + ['yes_not_with_me', 'yes_with_me', 'yes_sometimes', 'prefer_not']),
            wants_children=random.choice(['want'] * 4 + ['open'] * 3 + ['not_sure', 'dont_want', 'have_want_more']),
            love_languages=random.sample(['words', 'quality_time', 'acts', 'gifts', 'touch'], k=2),
            languages_spoken=list(dict.fromkeys(random.sample(
                ['en', 'en', 'lg', 'lg', 'sw', 'nyn', 'ach', 'xog', 'lgg', 'teo', 'cgg', 'nyo'],
                k=random.randint(2, 3)))),
        ))

        all_demo_ids.append(acc.id)
        created += 1

        if created % 50 == 0:
            db.session.commit()
            logger.info(f'[demo-seed] {created} profiles created ...')

    db.session.commit()
    logger.info(f'[demo-seed] Accounts: {created} created, {skipped} already existed.')

    # ═════════════════════════════════════════════════════════════════════════
    # Links — each demo account gets 4-10 connections
    # ═════════════════════════════════════════════════════════════════════════
    logger.info('[demo-seed] Creating links ...')
    link_pairs   = set()
    links_created = 0

    for idx, acc_id in enumerate(all_demo_ids):
        n          = random.randint(4, 10)
        candidates = random.sample(
            [aid for aid in all_demo_ids if aid != acc_id],
            k=min(n, len(all_demo_ids) - 1),
        )
        for other_id in candidates:
            pair = tuple(sorted([acc_id, other_id]))
            if pair in link_pairs: continue
            if Link.query.filter_by(requester_id=acc_id, addressee_id=other_id).first(): continue
            if Link.query.filter_by(requester_id=other_id, addressee_id=acc_id).first(): continue
            link_pairs.add(pair)
            db.session.add(Link(
                id=gen_id(), requester_id=acc_id, addressee_id=other_id,
                status='accepted',
                strength_score=round(random.uniform(0.3, 1.0), 2),
                created_at=dago(random.randint(1, 200)),
            ))
            links_created += 1
        if links_created % 300 == 0 and links_created:
            db.session.commit()

    db.session.commit()
    logger.info(f'[demo-seed] {links_created} links created.')

    # ═════════════════════════════════════════════════════════════════════════
    # Spark actions — populate deck so existing test accounts see profiles
    # ═════════════════════════════════════════════════════════════════════════
    logger.info('[demo-seed] Creating spark actions ...')
    male_ids   = all_demo_ids[:min(250, len(all_demo_ids))]
    female_ids = all_demo_ids[min(250, len(all_demo_ids)):]
    sparks_n   = 0

    # Subset of males spark females
    for m_id in male_ids[:120]:
        targets = random.sample(female_ids, k=min(random.randint(3, 10), len(female_ids)))
        for f_id in targets:
            if not Spark.query.filter_by(actor_id=m_id, target_id=f_id).first():
                db.session.add(Spark(
                    id=gen_id(), actor_id=m_id, target_id=f_id,
                    action=random.choice(['spark_up', 'spark_up', 'pass']),
                ))
                sparks_n += 1

    # Subset of females spark males back (creates mutual matches)
    for f_id in female_ids[:90]:
        targets = random.sample(male_ids, k=min(random.randint(2, 8), len(male_ids)))
        for m_id in targets:
            if not Spark.query.filter_by(actor_id=f_id, target_id=m_id).first():
                db.session.add(Spark(
                    id=gen_id(), actor_id=f_id, target_id=m_id,
                    action=random.choice(['spark_up', 'pass']),
                ))
                sparks_n += 1

    db.session.commit()
    logger.info(f'[demo-seed] {sparks_n} spark actions seeded.')
    logger.info('[demo-seed] ✓ Done! 500 demo profiles ready. Login: any +256700XXXXXX / linkup2026')


if __name__ == '__main__':
    seed()
