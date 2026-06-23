"""
LinkUp — 50 rich job seeds for Uganda's professional market.
Run standalone:  python -m backend.seed_jobs
Or called from   backend/seed.py  via seed_jobs()
"""
import uuid, json, logging
from datetime import datetime, timedelta

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def gen_id(): return str(uuid.uuid4())
def now():    return datetime.utcnow()
def days_ago(n): return now() - timedelta(days=n)
def days_ahead(n): return now() + timedelta(days=n)


# ─────────────────────────────────────────────────────────────────────────────
# 50 Job definitions
# Each tuple:
#   (title, org_name, poster_handle, emp_type, work_mode, seniority,
#    location_key,  salary_min, salary_max,
#    referral_open, skills[], requirements[], description)
# ─────────────────────────────────────────────────────────────────────────────

JOB_DEFS = [

    # ── Technology ─────────────────────────────────────────────────────────

    (
        'Senior Flutter Developer',
        'Andela',
        'samuel-ocen',
        'full_time', 'remote', 'senior',
        'kampala',
        6_000_000, 10_000_000,
        True,
        ['Flutter', 'Dart', 'Firebase', 'REST APIs', 'CI/CD', 'BLoC/Riverpod'],
        [
            '4+ years of Flutter development with shipped Play Store / App Store apps',
            'Strong grasp of state management (BLoC, Riverpod, or Provider)',
            'Experience integrating RESTful and WebSocket APIs',
            'Familiarity with CI/CD pipelines (GitHub Actions, Fastlane)',
            'Excellent code review skills and passion for clean architecture',
        ],
        """We are looking for a Senior Flutter Developer to join our growing mobile team at Andela.
You will design, build and maintain high-quality mobile applications that serve millions of users across East Africa.

**What you will do:**
- Lead the technical design of new mobile features from concept to launch
- Collaborate with product, design and backend teams in an agile environment
- Mentor junior developers and conduct thorough code reviews
- Optimise app performance and lead mobile testing strategy
- Contribute to our open-source Flutter tooling

**Who we are looking for:**
Someone who takes ownership, writes clean and testable code, and is passionate about mobile experiences in the African context. Remote-first culture; we value outcomes over attendance.
""",
    ),

    (
        'Backend Engineer – Python/Flask',
        'Bandwidth & Cloud Services',
        'henry-kiwanuka',
        'full_time', 'hybrid', 'mid',
        'kampala',
        4_000_000, 7_000_000,
        True,
        ['Python', 'Flask', 'SQLAlchemy', 'PostgreSQL', 'Redis', 'Docker'],
        [
            '3+ years of Python backend development',
            'Experience with Flask or FastAPI and RESTful API design',
            'Solid understanding of relational databases (PostgreSQL or MySQL)',
            'Familiarity with Docker and containerised deployments',
            'Experience with Redis caching or similar',
        ],
        """Bandwidth & Cloud Services is Uganda's leading cloud infrastructure provider. We are hiring a Backend Engineer to help us build scalable APIs powering our enterprise clients.

You will work closely with our DevOps and frontend teams to design reliable, secure and fast backend services.

**Responsibilities:**
- Design and implement RESTful APIs consumed by web and mobile clients
- Write clean, well-tested Python code following best practices
- Participate in database schema design and migrations
- Monitor and optimise slow queries and memory usage
- Contribute to architecture decisions for new product modules
""",
    ),

    (
        'Data Scientist – AgTech',
        'NITA-Uganda',
        'david-ochieng',
        'full_time', 'onsite', 'mid',
        'kampala',
        3_500_000, 6_000_000,
        False,
        ['Python', 'pandas', 'scikit-learn', 'SQL', 'Power BI', 'Machine Learning'],
        [
            'BSc or MSc in Statistics, Computer Science, or related field',
            '2+ years of applied data science or ML engineering experience',
            'Proficiency in Python (pandas, scikit-learn, matplotlib)',
            'Strong SQL skills for complex data extraction',
            'Experience presenting insights to non-technical stakeholders',
        ],
        """NITA-Uganda (National Information Technology Authority) is recruiting a Data Scientist to join our analytics unit. You will analyse large government and agricultural datasets to drive digital transformation across Uganda.

The ideal candidate is comfortable working with messy, real-world data and can translate findings into actionable policy recommendations.

**Key responsibilities:**
- Build predictive models for agricultural yield and climate risk
- Develop dashboards for senior government stakeholders
- Collaborate with field teams to ensure data quality
- Present findings to the Ministry of Agriculture and ICT
""",
    ),

    (
        'Product Manager – Fintech',
        'Stanbic Bank Uganda',
        'aisha-nakayima',
        'full_time', 'hybrid', 'senior',
        'kampala',
        7_000_000, 12_000_000,
        True,
        ['Product Strategy', 'Agile', 'Figma', 'SQL', 'User Research', 'Mobile Banking'],
        [
            '5+ years of product management experience, preferably in fintech or banking',
            'Proven record of shipping digital products from 0 to 1',
            'Strong data literacy — comfortable with SQL and analytics dashboards',
            'Experience running user research and translating insights into features',
            'Excellent stakeholder management at C-suite level',
        ],
        """Stanbic Bank Uganda is looking for a seasoned Product Manager to lead our digital banking product suite. You will own the roadmap for our mobile banking app used by over 1 million Ugandans.

This is a high-impact role that sits at the intersection of technology, finance, and user experience.

**What you will own:**
- Product vision and roadmap for the Stanbic Uganda mobile app
- Cross-functional delivery with engineering, design, compliance and marketing
- OKR setting and measurement for digital product metrics
- Competitive landscape analysis and feature prioritisation
- Regulatory engagement with Bank of Uganda on digital product compliance
""",
    ),

    (
        'DevOps / Cloud Engineer',
        'Bandwidth & Cloud Services',
        'henry-kiwanuka',
        'full_time', 'remote', 'senior',
        'kampala',
        6_000_000, 9_000_000,
        False,
        ['AWS', 'Terraform', 'Kubernetes', 'Docker', 'CI/CD', 'Linux', 'Monitoring'],
        [
            '4+ years of DevOps or SRE experience',
            'Hands-on with AWS or GCP (certifications a plus)',
            'Experience with Kubernetes orchestration and Helm charts',
            'Infrastructure-as-Code with Terraform or Pulumi',
            'Strong Linux sysadmin skills',
            'Experience with observability tools (Prometheus, Grafana, Loki)',
        ],
        """We are expanding our infrastructure team at Bandwidth & Cloud Services and need a senior DevOps engineer to design and operate cloud infrastructure for our enterprise clients.

**Your day-to-day:**
- Build and maintain scalable, highly-available Kubernetes clusters
- Define infrastructure-as-code standards for the organisation
- Design CI/CD pipelines for 20+ microservices
- Implement security best practices: IAM, secret management, network policies
- Lead incident response and post-mortem culture
""",
    ),

    (
        'UI/UX Designer',
        'Jumia Uganda',
        'aisha-nakayima',
        'full_time', 'onsite', 'mid',
        'kampala',
        2_500_000, 5_000_000,
        False,
        ['Figma', 'User Research', 'Prototyping', 'Design Systems', 'Usability Testing'],
        [
            '3+ years of product design experience for mobile or web',
            'Expert-level Figma skills including component libraries',
            'Experience running usability tests and synthesising insights',
            'Portfolio demonstrating end-to-end design process',
            'Understanding of accessibility and inclusive design',
        ],
        """Jumia Uganda is looking for a talented UI/UX Designer to join our product team. You will shape the experience of millions of Ugandans who shop on Jumia daily.

We need someone who is as comfortable sketching on paper as they are building pixel-perfect Figma prototypes.

**Responsibilities:**
- Lead design for key features across Jumia Uganda web and app
- Run weekly user research sessions with Kampala shoppers
- Build and maintain the Jumia Uganda design system
- Work closely with engineers to ensure pixel-perfect implementation
- Advocate for the user in all product discussions
""",
    ),

    (
        'iOS Developer',
        'Andela',
        'samuel-ocen',
        'contract', 'remote', 'senior',
        'kampala',
        7_000_000, 11_000_000,
        True,
        ['Swift', 'SwiftUI', 'Xcode', 'REST APIs', 'Core Data', 'TestFlight'],
        [
            '4+ years of native iOS development',
            'Strong Swift and SwiftUI skills',
            'Experience releasing apps on the App Store (links required)',
            'Knowledge of Apple Human Interface Guidelines',
            'Experience with automated testing (XCTest)',
        ],
        """Andela is placing a Senior iOS Developer with one of our enterprise clients in the fintech space. You will be embedded in a cross-functional team building a next-generation payments app for the East African market.

6-month contract, extendable. 100% remote.
""",
    ),

    (
        'Machine Learning Engineer',
        'Makerere University AI Lab',
        'david-ochieng',
        'full_time', 'onsite', 'senior',
        'kampala',
        5_000_000, 9_000_000,
        False,
        ['Python', 'PyTorch', 'TensorFlow', 'NLP', 'Computer Vision', 'MLflow'],
        [
            'MSc or PhD in Computer Science, AI, or related field preferred',
            '3+ years of applied ML experience in production environments',
            'Experience with NLP pipelines, preferably for low-resource languages',
            'Familiarity with MLOps tools (MLflow, DVC, Weights & Biases)',
            'Strong Python and mathematical foundations',
        ],
        """The Makerere University Artificial Intelligence Lab (AI Lab) is hiring a Machine Learning Engineer to join our research team. We build AI systems for African contexts — from disease detection to local-language processing.

**Projects you may work on:**
- Low-resource NLP models for Luganda and Swahili
- Crop disease detection using satellite imagery
- Maternal health risk prediction for rural Uganda
- Collaborative work with global partners (Google, Microsoft Research Africa)

This role combines research excellence with real-world impact.
""",
    ),

    (
        'Cybersecurity Analyst',
        'NITA-Uganda',
        'samuel-ocen',
        'full_time', 'onsite', 'mid',
        'kampala',
        3_500_000, 6_500_000,
        False,
        ['Network Security', 'SIEM', 'Penetration Testing', 'ISO 27001', 'Incident Response'],
        [
            '3+ years in cybersecurity or information security',
            'Experience with SIEM platforms (Splunk, QRadar, or similar)',
            'Knowledge of OWASP Top 10 and secure coding practices',
            'CompTIA Security+ or CEH certification preferred',
            'Familiarity with Uganda Cybercrime Act and data protection laws',
        ],
        """NITA-Uganda protects the digital infrastructure of the Government of Uganda. We are hiring a Cybersecurity Analyst to strengthen our national SOC team.

**What you will do:**
- Monitor government network infrastructure for threats and anomalies
- Conduct vulnerability assessments and penetration tests on GOU systems
- Investigate and respond to security incidents
- Develop security awareness training for government employees
- Contribute to national cybersecurity policy frameworks
""",
    ),

    (
        'Full-Stack JavaScript Developer',
        'Flutterwave Africa',
        'henry-kiwanuka',
        'full_time', 'remote', 'mid',
        'kampala',
        4_500_000, 8_000_000,
        True,
        ['React', 'Node.js', 'TypeScript', 'PostgreSQL', 'GraphQL', 'AWS'],
        [
            '3+ years of full-stack development with React and Node.js',
            'Strong TypeScript skills on both frontend and backend',
            'Experience with PostgreSQL and database optimisation',
            'Familiarity with payments APIs (Flutterwave, Stripe, or similar)',
            'Understanding of financial compliance and security requirements',
        ],
        """Flutterwave is building the payments infrastructure for Africa. We are looking for a Full-Stack Engineer to join our Uganda team and help scale payment flows across East Africa.

**Your impact:**
- Build merchant-facing dashboard features used by thousands of Ugandan businesses
- Design and implement robust payment processing microservices
- Integrate with mobile money APIs (MTN MoMo, Airtel Money)
- Collaborate with our Pan-African engineering teams in Lagos, Nairobi and Cairo
""",
    ),

    (
        'Technical Product Manager – Mobile',
        'SafeBoda Uganda',
        'aisha-nakayima',
        'full_time', 'hybrid', 'senior',
        'kampala',
        6_000_000, 10_000_000,
        True,
        ['Product Management', 'SQL', 'A/B Testing', 'Agile', 'Mobile UX'],
        [
            '4+ years of product management with a technical background',
            'Experience with consumer mobile apps at scale (100k+ DAU)',
            'Strong SQL skills and comfort with A/B test analysis',
            'Ability to write detailed product specs and PRDs',
            'Understanding of ride-hailing or logistics product dynamics',
        ],
        """SafeBoda is transforming urban mobility in Kampala. As Technical Product Manager for our rider app, you will define the product strategy and execution for our core mobility experience.

This role requires someone who can talk engineering with engineers, design with designers, and impact with the CEO.
""",
    ),

    (
        'React Native Developer',
        'Yo! Payments',
        'samuel-ocen',
        'full_time', 'remote', 'mid',
        'kampala',
        3_500_000, 6_000_000,
        False,
        ['React Native', 'JavaScript', 'TypeScript', 'Redux', 'REST APIs', 'Android'],
        [
            '2+ years of React Native development',
            'Published apps on Play Store and/or App Store',
            'Strong JavaScript/TypeScript fundamentals',
            'Experience with Redux or Zustand for state management',
            'Knowledge of mobile money API integration (MTN, Airtel, or Yo!)',
        ],
        """Yo! Payments is one of Uganda's oldest mobile money aggregators. We are looking for a React Native Developer to modernise our mobile app and bring a new generation of payment features to Ugandan consumers.
""",
    ),

    (
        'QA Engineer – Mobile & Web',
        'Andela',
        'robert-musinguzi',
        'full_time', 'remote', 'mid',
        'kampala',
        3_000_000, 5_500_000,
        False,
        ['Selenium', 'Cypress', 'Appium', 'JIRA', 'API Testing', 'Test Planning'],
        [
            '3+ years of software testing experience covering web and mobile',
            'Experience with test automation frameworks (Cypress, Selenium, Appium)',
            'Strong understanding of QA methodologies and test lifecycle',
            'Ability to write clear, reproducible bug reports',
            'Experience with API testing tools (Postman, Newman)',
        ],
        """Andela is placing a QA Engineer with our client — a fast-growing SaaS company building accounting software for African SMEs. You will define and execute quality standards across web and mobile platforms.
""",
    ),

    (
        'Data Engineer',
        'Makerere University AI Lab',
        'david-ochieng',
        'full_time', 'hybrid', 'mid',
        'kampala',
        4_000_000, 7_000_000,
        True,
        ['Python', 'Apache Spark', 'dbt', 'Airflow', 'PostgreSQL', 'BigQuery'],
        [
            '3+ years of data engineering experience',
            'Experience building ETL/ELT pipelines at scale',
            'Proficiency with dbt for data transformation',
            'Experience orchestrating workflows with Apache Airflow',
            'Strong SQL skills and understanding of data warehouse concepts',
        ],
        """We are building the data infrastructure for the next generation of African AI. The Makerere AI Lab is hiring a Data Engineer to build reliable data pipelines that power our ML research and partner projects.
""",
    ),

    (
        'Scrum Master / Agile Coach',
        'Bandwidth & Cloud Services',
        'grace-atim',
        'full_time', 'onsite', 'senior',
        'kampala',
        4_500_000, 7_000_000,
        False,
        ['Scrum', 'Kanban', 'Jira', 'Confluence', 'Agile Coaching', 'SAFe'],
        [
            'CSM or PSM I certification required; CSP or ICP-ACC preferred',
            '4+ years of Scrum Master or Agile Coach experience',
            'Experience facilitating distributed engineering teams',
            'Strong conflict resolution and facilitation skills',
            'Familiarity with JIRA and Confluence administration',
        ],
        """Bandwidth & Cloud Services is scaling engineering delivery and needs a Scrum Master to bring consistent Agile practices to our growing product teams. You will facilitate 4 cross-functional squads building cloud products.
""",
    ),

    # ── Finance & Banking ───────────────────────────────────────────────────

    (
        'Credit Risk Analyst',
        'dfcu Bank',
        'brian-ssemwogerere',
        'full_time', 'onsite', 'mid',
        'kampala',
        3_500_000, 6_000_000,
        False,
        ['Credit Analysis', 'Excel', 'SQL', 'Financial Modelling', 'Risk Management'],
        [
            'Bachelor\'s in Finance, Economics, or Accounting',
            '2+ years in credit risk, lending, or financial analysis',
            'Strong Excel modelling skills (scenario analysis, sensitivity models)',
            'Knowledge of Bank of Uganda credit guidelines',
            'CFA Level I candidate or equivalent preferred',
        ],
        """dfcu Bank is one of Uganda's largest commercial banks and we are looking for a Credit Risk Analyst to strengthen our SME lending desk.

You will assess loan applications, build financial models, and present credit recommendations to the Risk Committee.

**Key duties:**
- Evaluate creditworthiness of SME and corporate loan applicants
- Build and maintain financial models for borrower analysis
- Monitor portfolio performance and flag early warning signals
- Prepare credit papers for review by the Credit Committee
- Ensure compliance with Bank of Uganda prudential guidelines
""",
    ),

    (
        'Treasury Manager',
        'Stanbic Bank Uganda',
        'brian-ssemwogerere',
        'full_time', 'onsite', 'senior',
        'kampala',
        8_000_000, 14_000_000,
        False,
        ['Treasury', 'Forex', 'Liquidity Management', 'Bloomberg', 'Financial Modelling'],
        [
            '6+ years in treasury management at a commercial bank',
            'Experience trading forex and fixed income instruments',
            'Proficiency with Bloomberg terminal or Reuters Eikon',
            'Deep understanding of Bank of Uganda monetary policy',
            'ACI Dealing Certificate preferred',
        ],
        """Stanbic Bank Uganda seeks an experienced Treasury Manager to lead our FX trading desk and liquidity management function. This is a senior role reporting to the CFO.

You will manage daily liquidity positions, oversee FX trading, and provide market intelligence to senior leadership.
""",
    ),

    (
        'Finance Officer – Grants',
        'Makerere University',
        'brian-ssemwogerere',
        'full_time', 'onsite', 'entry',
        'kampala',
        1_800_000, 3_000_000,
        False,
        ['QuickBooks', 'Grant Reporting', 'Excel', 'Budget Management', 'Donor Compliance'],
        [
            'Bachelor\'s in Finance, Accounting, or Commerce',
            'Experience with donor-funded projects (USAID, EU, or World Bank preferred)',
            'Proficiency in QuickBooks and MS Excel',
            'Understanding of IFRS and Uganda tax regulations',
            'ACCA Part II or CPA (U) foundation level',
        ],
        """Makerere University\'s Research and Innovations Fund is seeking a Finance Officer to manage grant-funded research budgets. You will ensure compliance with donor reporting requirements and maintain accurate financial records for 15+ active grants.
""",
    ),

    (
        'Mobile Money Product Lead',
        'MTN Uganda',
        'felix-mugisha',
        'full_time', 'onsite', 'senior',
        'kampala',
        8_000_000, 14_000_000,
        True,
        ['Mobile Money', 'Product Management', 'Fintech', 'API Integration', 'Customer Journey'],
        [
            '5+ years of product or business development in mobile financial services',
            'Deep understanding of MTN MoMo ecosystem (or Airtel Money)',
            'Experience launching consumer financial products in Uganda',
            'Strong commercial acumen and ability to read financial P&Ls',
            'Stakeholder management across regulatory, technical, and commercial teams',
        ],
        """MTN Uganda is looking for a Mobile Money Product Lead to drive growth of MoMo — Uganda\'s most used mobile money service with over 12 million registered users.

You will own the product roadmap for merchant payments, savings products, and credit integrations.
""",
    ),

    (
        'Internal Audit Manager',
        'Centenary Bank Uganda',
        'brian-ssemwogerere',
        'full_time', 'onsite', 'senior',
        'kampala',
        6_000_000, 10_000_000,
        False,
        ['Internal Audit', 'Risk-Based Auditing', 'ACL Analytics', 'IIA Standards', 'Compliance'],
        [
            '6+ years in internal audit at a commercial bank or large financial institution',
            'CPA (U) or ACCA qualified — CIA certification a strong plus',
            'Experience applying IIA International Standards for Professional Practice',
            'Proficiency with audit data analytics tools (ACL, IDEA)',
            'Strong report writing and presentation skills',
        ],
        """Centenary Bank Uganda, the largest microfinance-oriented commercial bank, is looking for an Internal Audit Manager to lead our risk-based audit programme across 78 branches.

Reporting to the Board Audit Committee, you will drive a culture of accountability and internal controls.
""",
    ),

    (
        'Investment Analyst',
        'NSSF Uganda',
        'lawrence-nkurunziza',
        'full_time', 'onsite', 'mid',
        'kampala',
        4_000_000, 7_000_000,
        False,
        ['Equity Research', 'DCF Modelling', 'Financial Statements', 'Bloomberg', 'Portfolio Analysis'],
        [
            '3+ years in equity research, investment banking, or asset management',
            'CFA Level II or above preferred',
            'Strong financial modelling and valuation skills (DCF, comparables)',
            'Experience analysing East African listed equities',
            'Excellent written and verbal communication',
        ],
        """The National Social Security Fund (NSSF) Uganda manages over UGX 20 trillion in members\' savings. We are hiring an Investment Analyst to support our equity and fixed-income investment team.

You will conduct research on listed and unlisted companies, build valuation models, and present investment recommendations to the Investment Committee.
""",
    ),

    # ── Healthcare & Public Health ────────────────────────────────────────

    (
        'Public Health Officer – Nutrition',
        'Ministry of Health Uganda',
        'christine-akello',
        'full_time', 'onsite', 'mid',
        'kampala',
        2_500_000, 4_500_000,
        False,
        ['Nutrition Programming', 'SMART Survey', 'DHIS2', 'Community Health', 'M&E'],
        [
            'Bachelor\'s in Public Health, Nutrition, or Dietetics',
            '3+ years in nutrition programming in Uganda',
            'Experience conducting SMART surveys for nutrition assessments',
            'Proficiency with DHIS2 for health data management',
            'Fluency in at least one local language (Luganda, Acholi, or Runyakitara)',
        ],
        """The Ministry of Health Uganda is recruiting a Public Health Officer to coordinate national nutrition programmes across the Northern and Eastern regions.

You will work with district health teams, NGO partners, and communities to reduce malnutrition rates among children under five.
""",
    ),

    (
        'Clinical Pharmacist',
        'Cipla Quality Chemical Industries',
        'christine-akello',
        'full_time', 'onsite', 'mid',
        'kampala',
        3_500_000, 5_500_000,
        False,
        ['Clinical Pharmacy', 'Pharmaceutical Care', 'Drug Information', 'Regulatory Affairs', 'GMP'],
        [
            'Bachelor of Pharmacy (BPharm) from a recognised Ugandan university',
            'Licensed with the Uganda Pharmacy and Drugs Board',
            '3+ years of clinical pharmacy experience',
            'Knowledge of GMP standards for pharmaceutical manufacturing',
            'Experience with regulatory submissions to the NDA Uganda',
        ],
        """Cipla Quality Chemical Industries Limited (QCIL) — East Africa\'s largest pharmaceutical manufacturer — is hiring a Clinical Pharmacist to support our quality assurance and medical affairs teams in Kampala.
""",
    ),

    (
        'Mental Health Counsellor',
        'TPO Uganda',
        'olivia-nansubuga',
        'full_time', 'onsite', 'mid',
        'kampala',
        2_800_000, 4_200_000,
        False,
        ['Counselling', 'CBT', 'Trauma-Informed Care', 'MHPSS', 'Case Management'],
        [
            'Bachelor\'s in Psychology, Social Work, or Counselling',
            '3+ years of community-based mental health counselling',
            'Training in CBT and trauma-informed approaches',
            'Experience with conflict-affected and refugee populations',
            'Proficiency in English and Swahili or Luganda',
        ],
        """Transcultural Psychosocial Organisation (TPO) Uganda provides mental health and psychosocial support to vulnerable communities. We are hiring a Mental Health Counsellor to serve our Kampala urban programme.

You will provide individual and group counselling, case management, and community mental health education.
""",
    ),

    (
        'Hospital Administrator',
        'International Hospital Kampala',
        'grace-atim',
        'full_time', 'onsite', 'senior',
        'kampala',
        5_000_000, 8_000_000,
        False,
        ['Hospital Management', 'Healthcare Operations', 'Budget Management', 'Quality Improvement', 'HMIS'],
        [
            'Master\'s in Health Services Management or Business Administration',
            '5+ years of hospital or health facility administration',
            'Experience managing budgets above UGX 2 billion annually',
            'Knowledge of Ugandan Ministry of Health guidelines and accreditation standards',
            'Strong leadership and stakeholder engagement skills',
        ],
        """International Hospital Kampala is one of Uganda\'s most prestigious private hospitals. We are seeking an experienced Hospital Administrator to manage day-to-day operations, drive quality improvement, and ensure regulatory compliance.
""",
    ),

    (
        'Epidemiologist – Disease Surveillance',
        'Uganda National Institute of Public Health',
        'christine-akello',
        'full_time', 'onsite', 'senior',
        'kampala',
        4_500_000, 7_000_000,
        False,
        ['Epidemiology', 'DHIS2', 'R or STATA', 'Disease Surveillance', 'Field Investigations'],
        [
            'MPH or PhD in Epidemiology or related field',
            '4+ years of disease surveillance or outbreak investigation experience',
            'Proficiency in DHIS2 and epidemiological software (STATA, R, or Epi Info)',
            'Experience responding to disease outbreaks in resource-limited settings',
            'Published research or technical reports in epidemiology',
        ],
        """The Uganda National Institute of Public Health (UNIPH) is recruiting an Epidemiologist to lead disease surveillance and outbreak response activities. You will work with WHO, CDC, and UNICEF partners on national health security programmes.
""",
    ),

    # ── Government, NGO & Development ──────────────────────────────────────

    (
        'Programme Officer – Youth Empowerment',
        'UN Youth Uganda',
        'irene-nalubega',
        'full_time', 'onsite', 'mid',
        'kampala',
        3_000_000, 5_000_000,
        False,
        ['Programme Management', 'M&E', 'Proposal Writing', 'Stakeholder Engagement', 'Reporting'],
        [
            'Bachelor\'s in International Development, Social Sciences, or related',
            '3+ years of programme management with an NGO or UN agency',
            'Demonstrated experience in M&E framework design',
            'Strong proposal writing and donor reporting skills (UNDP, USAID, EU)',
            'Passion for youth development and gender equality',
        ],
        """UN Youth Uganda coordinates youth development programming in partnership with government and civil society. We are hiring a Programme Officer to manage our flagship youth empowerment grant across 10 Ugandan districts.

You will oversee field implementation, manage grantee relationships, and report to international donors.
""",
    ),

    (
        'Climate Change Adaptation Specialist',
        'UNDP Uganda',
        'noah-tumusiime',
        'full_time', 'hybrid', 'senior',
        'kampala',
        7_000_000, 12_000_000,
        False,
        ['Climate Policy', 'GCF Reporting', 'Environmental Assessment', 'NDC', 'Community Adaptation'],
        [
            'Master\'s in Environmental Science, Climate Change, or related field',
            '5+ years of climate change programming in sub-Saharan Africa',
            'Experience with Green Climate Fund (GCF) project cycle',
            'Knowledge of Uganda\'s National Determined Contributions (NDC)',
            'Fluency in English; French a plus',
        ],
        """UNDP Uganda is implementing Uganda\'s National Climate Change Adaptation programme with USD 40 million from the Green Climate Fund. We need a senior specialist to lead the technical delivery of climate resilience interventions in 15 districts.
""",
    ),

    (
        'WASH Engineer',
        'National Water and Sewerage Corporation',
        'james-oryem',
        'full_time', 'onsite', 'mid',
        'gulu',
        3_000_000, 5_000_000,
        False,
        ['WASH', 'Civil Engineering', 'AutoCAD', 'Water Systems Design', 'Community Mobilisation'],
        [
            'BSc in Civil Engineering, Water Engineering, or Environmental Engineering',
            '3+ years of WASH project design and supervision',
            'Experience designing water supply and sanitation systems for peri-urban areas',
            'Proficiency in AutoCAD and GIS software',
            'Willingness to be field-based in Northern Uganda',
        ],
        """The National Water and Sewerage Corporation (NWSC) is extending safe water and sanitation services to underserved areas of Northern Uganda. We are hiring a WASH Engineer to design and supervise infrastructure projects in Gulu and surrounding areas.
""",
    ),

    (
        'Agricultural Extension Officer',
        'Grameen Foundation Uganda',
        'noah-tumusiime',
        'full_time', 'onsite', 'entry',
        'mbale',
        1_500_000, 2_800_000,
        False,
        ['Agronomy', 'Community Extension', 'Farmer Training', 'Digital Agriculture', 'Report Writing'],
        [
            'Bachelor\'s in Agriculture, Agronomy, or Agricultural Extension',
            '1–2 years of field-based agricultural extension work',
            'Experience using digital tools for farmer engagement (e-extension, e-voucher)',
            'Fluency in Lugisu or Lumasaba language strongly preferred',
            'Valid motorcycle riding licence',
        ],
        """Grameen Foundation Uganda is empowering smallholder farmers in Eastern Uganda through digital agriculture solutions. As an Agricultural Extension Officer, you will train farmers on improved practices and connect them to digital markets.

Based in Mbale, with frequent travel to Sironko, Bududa, and Manafwa districts.
""",
    ),

    (
        'Legal Officer – Commercial Law',
        'KCCA',
        'kate-achieng',
        'full_time', 'onsite', 'mid',
        'kampala',
        3_500_000, 6_000_000,
        False,
        ['Commercial Law', 'Contract Drafting', 'Regulatory Compliance', 'Litigation', 'Land Law'],
        [
            'LLB degree from a recognised university; Postgraduate Diploma in Legal Practice',
            'Enrolled Advocate of the Courts of Judicature of Uganda',
            '3+ years of commercial or public sector legal practice',
            'Experience with procurement law and public contracts',
            'Knowledge of Ugandan land and property law',
        ],
        """Kampala Capital City Authority (KCCA) is seeking a Legal Officer to support the Legal and Corporate Affairs division. You will handle commercial contracts, land matters, litigation, and regulatory compliance for Kampala\'s city authority.
""",
    ),

    # ── Telecommunications ─────────────────────────────────────────────────

    (
        'Network Planning Engineer – 5G',
        'MTN Uganda',
        'felix-mugisha',
        'full_time', 'onsite', 'senior',
        'kampala',
        7_000_000, 12_000_000,
        False,
        ['5G NR', 'RF Planning', 'Atoll', 'Network Optimisation', 'Site Acquisition', 'LTE'],
        [
            '5+ years of network planning in mobile telecommunications',
            'Experience with 5G NR deployment in sub-Saharan Africa',
            'Proficiency in RF planning tools (Atoll, ASSET, or Planet)',
            'Understanding of 3GPP standards for 5G stand-alone and non-stand-alone',
            'Experience managing tower companies and passive infrastructure',
        ],
        """MTN Uganda is accelerating its 5G rollout across Kampala and major Ugandan towns. We need a Senior Network Planning Engineer to lead the technical design and deployment strategy for our 5G NR network.
""",
    ),

    (
        'Telecoms Sales Manager',
        'Airtel Uganda',
        'felix-mugisha',
        'full_time', 'onsite', 'senior',
        'kampala',
        5_000_000, 9_000_000,
        True,
        ['B2B Sales', 'Enterprise Telecoms', 'CRM', 'Account Management', 'Negotiation'],
        [
            '5+ years of B2B sales in telecoms or ICT',
            'Strong existing network of corporate decision-makers in Uganda',
            'Track record of achieving >120% of sales quota',
            'Experience with Salesforce or similar CRM',
            'Excellent presentation and negotiation skills',
        ],
        """Airtel Uganda is growing its enterprise business division and needs a Sales Manager to lead a team of 8 account managers selling connectivity, cloud, and managed IT services to Ugandan corporates.
""",
    ),

    (
        'Fibre Network Technician',
        'Liquid Telecom Uganda',
        'felix-mugisha',
        'full_time', 'onsite', 'entry',
        'kampala',
        1_200_000, 2_200_000,
        False,
        ['Fibre Optics', 'OTDR', 'Cable Splicing', 'Network Troubleshooting', 'Safety'],
        [
            'Diploma or degree in Electrical Engineering or Telecommunications',
            '1+ year of fibre optic installation and splicing experience',
            'Experience using OTDR and optical power meters',
            'Physical fitness for field work including trenching and climbing',
            'Valid driving licence',
        ],
        """Liquid Telecom Uganda (now Liquid Intelligent Technologies) is expanding its fibre backbone across Kampala. We are hiring Fibre Network Technicians to join our field operations team for installation, maintenance, and fault resolution.
""",
    ),

    (
        'VoIP / Unified Communications Engineer',
        'Smile Communications Uganda',
        'felix-mugisha',
        'full_time', 'hybrid', 'mid',
        'kampala',
        3_000_000, 5_500_000,
        False,
        ['VoIP', 'Cisco UCM', 'SIP', 'Asterisk', 'IP Telephony', 'Network Configuration'],
        [
            '3+ years of VoIP and unified communications engineering',
            'Hands-on experience with Cisco Unified Communications Manager (UCM)',
            'Strong understanding of SIP protocols and SBC configuration',
            'Experience deploying and managing Asterisk PBX systems',
            'CCNA or CCNP Collaboration preferred',
        ],
        """Smile Communications Uganda delivers broadband and managed services to East African enterprises. We need a VoIP Engineer to design and support unified communications solutions for our corporate client base.
""",
    ),

    (
        'Regulatory Affairs Manager – Telecoms',
        'Airtel Uganda',
        'kate-achieng',
        'full_time', 'onsite', 'senior',
        'kampala',
        6_000_000, 10_000_000,
        False,
        ['Telecoms Regulation', 'UCC', 'Policy Analysis', 'Spectrum Management', 'Compliance'],
        [
            'LLB or BSc in Telecommunications Engineering; Master\'s preferred',
            '5+ years in telecoms regulatory affairs',
            'Deep knowledge of Uganda Communications Commission (UCC) regulations',
            'Experience engaging with UCC, ITU, and CRASA',
            'Excellent written communication and policy drafting skills',
        ],
        """Airtel Uganda needs a Regulatory Affairs Manager to manage our relationship with the Uganda Communications Commission and lead spectrum licensing, numbering, and interconnect regulation matters.
""",
    ),

    # ── E-commerce & Retail ─────────────────────────────────────────────────

    (
        'E-commerce Operations Manager',
        'Jumia Uganda',
        'irene-nalubega',
        'full_time', 'onsite', 'senior',
        'kampala',
        4_500_000, 8_000_000,
        True,
        ['E-commerce Operations', 'Logistics', 'Inventory Management', 'SQL', 'Cross-functional Leadership'],
        [
            '4+ years in e-commerce or logistics operations',
            'Experience managing fulfilment centres and last-mile delivery in Uganda',
            'Strong analytical skills — comfortable with SQL and Excel at scale',
            'Demonstrated people management skills (10+ direct reports)',
            'Understanding of reverse logistics and customer returns management',
        ],
        """Jumia Uganda processes thousands of orders daily. Our Operations Manager will lead the end-to-end logistics and warehouse operation in Kampala, driving efficiency, reducing cost, and improving customer satisfaction.
""",
    ),

    (
        'Digital Marketing Manager',
        'Jumia Uganda',
        'irene-nalubega',
        'full_time', 'onsite', 'mid',
        'kampala',
        3_000_000, 5_500_000,
        False,
        ['Google Ads', 'Meta Ads', 'Email Marketing', 'SEO', 'Analytics', 'Content Strategy'],
        [
            '3+ years of digital marketing experience in e-commerce or FMCG',
            'Hands-on experience managing Google Ads and Meta Ads campaigns',
            'Strong understanding of SEO and content marketing',
            'Proficiency with Google Analytics 4 and Meta Business Suite',
            'Experience with email marketing automation (Mailchimp, Brevo)',
        ],
        """Jumia Uganda is looking for a Digital Marketing Manager to lead our performance marketing, SEO, and CRM programmes. You will manage a UGX 500M+ digital marketing budget and drive growth for Uganda\'s biggest online marketplace.
""",
    ),

    (
        'Customer Experience Lead',
        'Airtel Uganda',
        'grace-atim',
        'full_time', 'onsite', 'mid',
        'kampala',
        2_500_000, 4_500_000,
        False,
        ['Customer Service', 'NPS', 'CRM', 'Call Centre Management', 'Process Improvement'],
        [
            '3+ years in customer experience or call centre leadership',
            'Demonstrated improvement of NPS or CSAT scores in a previous role',
            'Experience with CRM systems (Salesforce, Zendesk, or Freshdesk)',
            'Strong people management and coaching skills',
            'Passion for service excellence in telecom or FMCG',
        ],
        """Airtel Uganda is transforming our customer experience function and needs a CX Lead to oversee contact centre operations, drive NPS improvement, and build a customer-first culture across all touchpoints.
""",
    ),

    (
        'Retail Branch Manager',
        'DFCU Bank',
        'brian-ssemwogerere',
        'full_time', 'onsite', 'senior',
        'mbarara',
        4_000_000, 7_000_000,
        False,
        ['Branch Management', 'Sales', 'Credit', 'Team Leadership', 'Banking Operations'],
        [
            '5+ years of banking experience with at least 2 years in branch management',
            'Strong sales track record in retail or SME banking',
            'Thorough knowledge of Bank of Uganda prudential regulations',
            'Demonstrated people management skills (15+ direct reports)',
            'Willingness to be based in Mbarara',
        ],
        """dfcu Bank is looking for a Retail Branch Manager to lead our Mbarara branch — one of our busiest upcountry locations. You will drive deposit mobilisation, loan disbursement, and customer satisfaction while managing 20 staff members.
""",
    ),

    # ── Education ─────────────────────────────────────────────────────────

    (
        'Computer Science Lecturer',
        'Makerere University',
        'mary-nakato',
        'full_time', 'onsite', 'mid',
        'kampala',
        2_500_000, 4_500_000,
        False,
        ['Computer Science', 'Python', 'Algorithms', 'Research', 'Curriculum Development'],
        [
            'Master\'s in Computer Science, Software Engineering, or related field',
            'PhD preferred or currently enrolled',
            '2+ years of university lecturing experience',
            'Research publications in peer-reviewed journals or conferences',
            'Ability to teach data structures, algorithms, and programming',
        ],
        """Makerere University\'s School of Computing and Informatics Technology is recruiting a Lecturer in Computer Science. You will teach undergraduate and postgraduate courses, supervise research, and contribute to curriculum development.
""",
    ),

    (
        'Secondary School Teacher – Mathematics',
        'St Mary\'s College Kisubi',
        'mary-nakato',
        'full_time', 'onsite', 'mid',
        'kampala',
        1_200_000, 2_000_000,
        False,
        ['Mathematics', 'Pedagogy', 'UNEB Curriculum', 'Classroom Management', 'Results Analysis'],
        [
            'Bachelor of Education (Mathematics) or Bachelor\'s + PGDE',
            'Registered with the Uganda National Teachers\' College',
            '3+ years of O-level and A-level Mathematics teaching',
            'Track record of excellent UNEB results',
            'Passion for STEM education in Uganda',
        ],
        """St Mary\'s College Kisubi, one of Uganda\'s top-performing secondary schools, is hiring a Mathematics Teacher for O and A levels. You will inspire students, drive academic excellence, and contribute to the school\'s rich heritage of academic achievement.
""",
    ),

    (
        'Education Programme Manager',
        'BRAC Uganda',
        'mary-nakato',
        'full_time', 'hybrid', 'senior',
        'kampala',
        3_500_000, 6_000_000,
        False,
        ['Programme Management', 'Education', 'M&E', 'Donor Reporting', 'Community Mobilisation'],
        [
            'Master\'s in Education, International Development, or related',
            '5+ years managing education programmes in Uganda',
            'Experience with USAID, DFID, or EU education grants',
            'Strong M&E skills and MEAL framework development',
            'Fluency in a Ugandan local language',
        ],
        """BRAC Uganda operates the largest non-state school network in East Africa. Our Education Programme Manager will oversee pre-primary and primary education programming for 80,000+ learners across Uganda.
""",
    ),

    (
        'Vocational Training Instructor – ICT',
        'Youth Alive Uganda',
        'mary-nakato',
        'full_time', 'onsite', 'mid',
        'gulu',
        1_500_000, 2_500_000,
        False,
        ['ICT Training', 'Computer Literacy', 'Web Design', 'MS Office', 'Youth Training'],
        [
            'Bachelor\'s in IT, Computer Science, or Education (IT)',
            '2+ years of ICT training experience with youth or adults',
            'Experience with blended learning platforms',
            'Fluency in English and Acholi strongly preferred',
            'Passion for youth economic empowerment',
        ],
        """Youth Alive Uganda is an NGO empowering young people in post-conflict Northern Uganda. We are hiring a Vocational Training Instructor to teach practical ICT skills — computer literacy, web design, and digital entrepreneurship — to youth aged 16–35 in Gulu.
""",
    ),

    # ── Agriculture & Environment ──────────────────────────────────────────

    (
        'AgriTech Product Manager',
        'Ensibuuko',
        'noah-tumusiime',
        'full_time', 'hybrid', 'mid',
        'kampala',
        3_500_000, 6_000_000,
        True,
        ['AgTech', 'Product Management', 'User Research', 'Mobile Agri-Finance', 'USSD'],
        [
            '3+ years of product management experience in AgTech, fintech, or mobile services',
            'Deep understanding of smallholder farmer needs in Uganda',
            'Experience designing for low-literacy and offline-first mobile users',
            'Familiarity with USSD, SMS, and feature phone product design',
            'Strong stakeholder management with development partners and investors',
        ],
        """Ensibuuko is a fintech platform serving savings groups and smallholder farmers in Uganda. As AgriTech Product Manager, you will own the roadmap for our digital savings and credit product used by 500,000+ rural Ugandans.
""",
    ),

    (
        'Environmental Impact Assessment Specialist',
        'National Environment Management Authority',
        'noah-tumusiime',
        'full_time', 'onsite', 'senior',
        'kampala',
        4_000_000, 7_000_000,
        False,
        ['EIA', 'Environmental Law', 'GIS', 'Environmental Monitoring', 'Stakeholder Consultation'],
        [
            'Master\'s in Environmental Science, Environmental Law, or Natural Resources',
            '5+ years conducting Environmental and Social Impact Assessments',
            'Knowledge of the National Environment Act and EIA Regulations of Uganda',
            'Proficiency in GIS (ArcGIS or QGIS)',
            'Experience in oil and gas, mining, or infrastructure sector EIAs',
        ],
        """NEMA Uganda is hiring a senior EIA Specialist to lead impact assessments for major infrastructure projects including the East Africa Crude Oil Pipeline (EACOP) and hydropower developments. You will interact with investors, government, and affected communities.
""",
    ),

    (
        'Agronomist – Coffee & Cocoa',
        'Olam Agri Uganda',
        'noah-tumusiime',
        'full_time', 'onsite', 'mid',
        'mbale',
        2_500_000, 4_500_000,
        False,
        ['Agronomy', 'Coffee', 'Farmer Training', 'Good Agricultural Practices', 'Supply Chain'],
        [
            'Bachelor\'s in Agriculture (specialisation in Crop Science or Agronomy)',
            '3+ years of field agronomy in coffee, cocoa, or similar cash crops',
            'Experience training farmer groups on GAPs and certification standards',
            'Knowledge of Rainforest Alliance or UTZ certification processes',
            'Motorcycle riding licence; willingness to travel extensively in Eastern Uganda',
        ],
        """Olam Agri Uganda sources coffee and cocoa from thousands of smallholder farmers in Eastern Uganda. We are hiring an Agronomist to lead farmer training, Good Agricultural Practice adoption, and sustainability certification programmes.
""",
    ),

    (
        'Renewable Energy Engineer',
        'Umeme Limited',
        'james-oryem',
        'full_time', 'hybrid', 'mid',
        'kampala',
        4_000_000, 7_000_000,
        False,
        ['Solar PV', 'Wind Energy', 'AutoCAD', 'Grid Integration', 'Energy Audits'],
        [
            'BSc in Electrical Engineering with renewable energy focus',
            '3+ years designing and supervising solar PV or mini-grid projects in Uganda',
            'Proficiency in PVsyst, SAM, or HOMER for energy system modelling',
            'Understanding of ERA Uganda grid connection requirements',
            'Registered Engineer with the Uganda Institution of Professional Engineers',
        ],
        """Umeme Limited is Uganda\'s main electricity distributor and is investing in renewable energy solutions to address load shedding and expand rural access. We are hiring a Renewable Energy Engineer to design and supervise solar hybrid projects and grid-edge solutions.
""",
    ),

    # ── Media & Marketing ─────────────────────────────────────────────────

    (
        'Brand Manager',
        'Roofings Group',
        'irene-nalubega',
        'full_time', 'onsite', 'mid',
        'kampala',
        3_000_000, 5_500_000,
        False,
        ['Brand Management', 'Trade Marketing', 'Consumer Insights', 'ATL/BTL', 'Media Planning'],
        [
            '3+ years of brand management experience in FMCG or manufacturing',
            'Experience managing ATL and BTL campaigns in Uganda',
            'Strong understanding of trade marketing and retailer relationships',
            'Proficiency with consumer research tools and brand tracking',
            'Excellent project management skills',
        ],
        """Roofings Group is one of Uganda\'s largest industrial manufacturers. We are looking for a Brand Manager to lead marketing for our steel, roofing, and construction products across Uganda and East Africa.
""",
    ),

    (
        'Journalist – Technology & Business',
        'The Independent Uganda',
        'peter-odeke',
        'full_time', 'hybrid', 'mid',
        'kampala',
        1_500_000, 2_800_000,
        False,
        ['Journalism', 'Investigative Reporting', 'Multimedia', 'SEO Writing', 'Data Journalism'],
        [
            '3+ years of journalism experience with a recognised Ugandan publication',
            'Portfolio of published technology or business investigative pieces',
            'Experience with data journalism and visualisation tools',
            'Understanding of Ugandan media law and ethical reporting standards',
            'Active presence on Twitter/X with established journalist following',
        ],
        """The Independent Uganda is hiring a Technology & Business journalist to cover Uganda\'s fast-growing tech startup ecosystem, banking sector, and regulatory environment. You will write long-form investigative pieces and break news on digital economy developments.
""",
    ),

    (
        'Social Media Manager',
        'MTN Uganda',
        'irene-nalubega',
        'full_time', 'hybrid', 'mid',
        'kampala',
        2_500_000, 4_500_000,
        False,
        ['Social Media', 'Content Creation', 'Community Management', 'Meta Ads', 'Analytics'],
        [
            '3+ years managing social media for a large brand in Uganda',
            'Expertise across Facebook, Instagram, X (Twitter), TikTok, and LinkedIn',
            'Strong copywriting skills in English and Luganda',
            'Experience with social listening tools (Brandwatch, Sprout Social)',
            'Ability to manage crisis communications and negative sentiment',
        ],
        """MTN Uganda has one of Uganda\'s largest social media followings (3M+). We are hiring a Social Media Manager to create compelling content, engage with customers, and drive brand love for the MTN brand across all digital platforms.
""",
    ),

    (
        'Graphic Designer – Brand & Digital',
        'Stanbic Bank Uganda',
        'aisha-nakayima',
        'full_time', 'hybrid', 'entry',
        'kampala',
        1_800_000, 3_000_000,
        False,
        ['Graphic Design', 'Adobe Creative Suite', 'Figma', 'Motion Design', 'Brand Guidelines'],
        [
            'Diploma or Bachelor\'s in Graphic Design or Visual Communication',
            '2+ years of brand design experience',
            'Expert proficiency in Adobe Creative Suite (Illustrator, Photoshop, InDesign)',
            'Experience producing assets for digital and print (social, brochures, OOH)',
            'Portfolio demonstrating strong visual identity and typography skills',
        ],
        """Stanbic Bank Uganda is hiring a Graphic Designer to produce high-quality marketing collateral for our retail banking and corporate communications teams. You will work with the brand and marketing team to create digital, print, and video assets.
""",
    ),

    # ── HR & People ────────────────────────────────────────────────────────

    (
        'HR Business Partner',
        'Cipla Quality Chemical Industries',
        'grace-atim',
        'full_time', 'onsite', 'senior',
        'kampala',
        4_500_000, 7_500_000,
        False,
        ['HRBP', 'Performance Management', 'Talent Acquisition', 'Employee Relations', 'HRIS'],
        [
            '5+ years of HR Business Partner experience in manufacturing or pharma',
            'Demonstrated expertise in Ugandan employment law',
            'Experience managing complex employee relations cases',
            'HRMI (U) membership or CIPD Level 5 equivalent',
            'Proficiency with HRIS systems (SAP SuccessFactors, BambooHR)',
        ],
        """Cipla QCIL employs over 500 people at our Kampala manufacturing facility. We need an experienced HRBP to partner with the Operations and Quality leadership teams, drive talent development, and ensure regulatory compliance in people matters.
""",
    ),

    (
        'Talent Acquisition Specialist',
        'Andela',
        'grace-atim',
        'full_time', 'remote', 'mid',
        'kampala',
        3_500_000, 6_000_000,
        True,
        ['Recruitment', 'Boolean Search', 'LinkedIn Recruiter', 'ATS', 'Employer Branding'],
        [
            '3+ years of technical recruiting experience',
            'Expert-level LinkedIn Recruiter skills',
            'Experience recruiting across multiple African countries simultaneously',
            'Familiarity with ATS platforms (Greenhouse, Lever, or Workday)',
            'Strong personal network in the East African tech talent community',
        ],
        """Andela connects African software engineers with global companies. We are hiring a Talent Acquisition Specialist to source, engage, and assess top engineers across Uganda, Kenya, and Nigeria for placement with our US and European clients.
""",
    ),

    (
        'Organisational Development Consultant',
        'UNDP Uganda',
        'grace-atim',
        'contract', 'hybrid', 'senior',
        'kampala',
        5_000_000, 9_000_000,
        False,
        ['OD Consulting', 'Change Management', 'Capacity Building', 'Facilitation', 'Report Writing'],
        [
            'Master\'s in Organisational Development, HRM, or Business Administration',
            '7+ years of OD consulting in the development sector',
            'Experience conducting institutional assessments for UN agencies or DFIs',
            'Strong facilitation skills for workshops and focus groups',
            'Published frameworks or tools for OD in sub-Saharan Africa',
        ],
        """UNDP Uganda is procuring an OD Consultant to lead a 6-month institutional capacity assessment and change management support programme for the Ministry of Public Service. The deliverable is a capacity development action plan and implementation roadmap.

6-month consultancy. Home-based with travel to Kampala for workshops.
""",
    ),

    # ── Hospitality & Other ────────────────────────────────────────────────

    (
        'Hotel General Manager',
        'Protea Hotel by Marriott Kampala',
        'peter-odeke',
        'full_time', 'onsite', 'senior',
        'kampala',
        9_000_000, 16_000_000,
        False,
        ['Hotel Management', 'Revenue Management', 'F&B Operations', 'Guest Experience', 'P&L Management'],
        [
            'Degree in Hospitality Management or Business Administration',
            '7+ years of hotel management with at least 3 years as GM or Deputy GM',
            'Proven track record of RevPAR growth in an international hotel brand',
            'Marriott Bonvoy brand standards experience preferred',
            'Exceptional interpersonal skills for managing international guests and ownership',
        ],
        """Protea Hotel by Marriott Kampala is a 4-star business hotel in the heart of Kampala. We are looking for an accomplished General Manager to lead all aspects of hotel operations, drive revenue growth, and deliver the Marriott guest experience.

Reporting to the Regional Director of Operations and hotel ownership board.
""",
    ),

    (
        'Uganda Airlines Cabin Crew',
        'Uganda Airlines',
        'peter-odeke',
        'full_time', 'onsite', 'entry',
        'kampala',
        1_800_000, 3_000_000,
        False,
        ['Safety Procedures', 'Customer Service', 'First Aid', 'Multilingual Communication', 'Grooming Standards'],
        [
            'Diploma or Bachelor\'s degree from a recognised institution',
            'Height between 5\'2" and 6\'1", with proportional weight',
            'Excellent customer service and communication skills',
            'Swimming certificate from a recognised swimming club',
            'Fluency in English; French or Arabic a significant advantage',
            'No visible tattoos or body piercings',
        ],
        """Uganda Airlines, the national carrier, is recruiting Cabin Crew to join our growing fleet. As the face of Uganda\'s national airline, you will ensure the safety, comfort, and satisfaction of passengers on domestic and international routes.

Training will be conducted at the Uganda Civil Aviation Authority training facility before deployment.
""",
    ),

    (
        'Supply Chain Manager',
        'Roofings Group',
        'james-oryem',
        'full_time', 'onsite', 'senior',
        'kampala',
        5_000_000, 9_000_000,
        False,
        ['Supply Chain Management', 'Procurement', 'Inventory Control', 'ERP (SAP)', 'Logistics'],
        [
            '6+ years of supply chain management in manufacturing or construction materials',
            'Hands-on experience with SAP ERP modules (MM, WM, PP)',
            'Strong supplier negotiation and contract management skills',
            'Knowledge of import/export regulations in Uganda and EAC',
            'Proficiency in demand planning and inventory optimisation',
        ],
        """Roofings Group manufactures steel, wire, and roofing materials for East Africa\'s construction market. We need a Supply Chain Manager to optimise procurement of raw materials (steel billets, wire rod, aluminium coil), manage our regional logistics network, and ensure on-time production supply.
""",
    ),

]


# ─────────────────────────────────────────────────────────────────────────────
# Location key → DB location variable name (resolved at seed time)
# ─────────────────────────────────────────────────────────────────────────────

LOCATION_KEYS = {
    'kampala': 'kampala',
    'mbarara': 'mbarara',
    'gulu':    'gulu',
    'mbale':   'mbale',
}


def seed_jobs(account_ids: dict, location_ids: dict):
    """
    Insert the 50 job definitions.
    :param account_ids: dict[handle → id] from seed.py
    :param location_ids: dict[key → id]  e.g. {'kampala': '...', ...}
    """
    from backend.models import db
    from backend.domains.jobs.models import Job

    inserted = 0
    for defn in JOB_DEFS:
        (title, org_name, poster_handle, emp_type, work_mode, seniority,
         loc_key, sal_min, sal_max, referral, skills, requirements, desc) = defn

        # Skip if already seeded by title
        if Job.query.filter_by(title=title).first():
            continue

        poster_id = account_ids.get(poster_handle)
        if not poster_id:
            logger.warning(f'[seed_jobs] Skipping "{title}" — unknown poster {poster_handle!r}')
            continue

        loc_id = location_ids.get(loc_key)

        # Vary created_at for a realistic feed (0–60 days ago)
        days_old = hash(title) % 60
        created  = days_ago(days_old)
        expires  = days_ahead(30 + (hash(title) % 60))

        job = Job(
            id              = gen_id(),
            posted_by       = poster_id,
            org_name        = org_name,
            title           = title,
            description     = desc.strip(),
            requirements    = requirements,
            location_id     = loc_id,
            location_text   = loc_key.capitalize() + ', Uganda',
            employment_type = emp_type,
            work_mode       = work_mode,
            seniority       = seniority,
            salary_min      = sal_min,
            salary_max      = sal_max,
            currency        = 'UGX',
            skills          = skills,
            is_open         = 1,
            referral_open   = int(referral),
            view_count      = hash(title) % 300,
            created_at      = created,
            expires_at      = expires,
        )
        db.session.add(job)
        inserted += 1

    db.session.commit()
    logger.info(f'[seed_jobs] Inserted {inserted} jobs')
    return inserted


# ── Standalone entry point ────────────────────────────────────────────────────

def run():
    from backend.app import create_app
    app = create_app()
    with app.app_context():
        from backend.domains.identity.models import Account
        from backend.domains.reference.models import Location

        account_ids = {
            a.handle: a.id
            for a in Account.query.filter(Account.deleted_at.is_(None)).all()
        }
        locs = Location.query.all()
        location_ids = {loc.name.lower(): loc.id for loc in locs}

        # Also map common keys
        for loc in locs:
            if 'kampala' in loc.name.lower(): location_ids['kampala'] = loc.id
            if 'mbarara' in loc.name.lower(): location_ids['mbarara'] = loc.id
            if 'gulu'    in loc.name.lower(): location_ids['gulu']    = loc.id
            if 'mbale'   in loc.name.lower(): location_ids['mbale']   = loc.id

        n = seed_jobs(account_ids, location_ids)
        print(f'Done — {n} jobs inserted.')


if __name__ == '__main__':
    run()
