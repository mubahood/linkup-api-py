"""
Seed 200 diverse posts across all user accounts.

Distribution:
  - Professional posts  ~130  (text, photo, article, poll, job_share, event_share)
  - Dating posts        ~45   (text, photo, status, poll)
  - Both mode           ~25   (life updates, reflections)

All timestamps spread across the last 60 days so the feed looks organic.
Engagement counts (likes, comments, views) are set realistically.
"""

import sys
import os
import uuid
import random
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.app import create_app
from backend.models import db
from backend.domains.identity.models import Account
from backend.domains.posts.models import Post, PostLike, PostComment, PostCommentLike, PostSave, PollVote

app = create_app()

# ── helpers ───────────────────────────────────────────────────────────────────

def rng_dt(days_ago_max=60, days_ago_min=0):
    delta = random.randint(days_ago_min * 1440, days_ago_max * 1440)
    return datetime.utcnow() - timedelta(minutes=delta)


def uid():
    return str(uuid.uuid4())


# ── Picsum photo sets by theme ────────────────────────────────────────────────

TECH_PHOTOS = [
    [{'url': 'https://picsum.photos/id/0/800/500',   'type': 'image', 'caption': 'Team building session'}],
    [{'url': 'https://picsum.photos/id/20/800/500',  'type': 'image', 'caption': 'Hackathon 2025'}],
    [{'url': 'https://picsum.photos/id/48/800/500',  'type': 'image', 'caption': 'Workshop'}],
    [{'url': 'https://picsum.photos/id/60/800/500',  'type': 'image', 'caption': 'Conference keynote'}],
    [{'url': 'https://picsum.photos/id/100/800/500', 'type': 'image', 'caption': 'Office view'}],
    [{'url': 'https://picsum.photos/id/119/800/500', 'type': 'image', 'caption': ''}],
    [{'url': 'https://picsum.photos/id/160/800/500', 'type': 'image', 'caption': 'Startup panel'}],
    [{'url': 'https://picsum.photos/id/180/800/500', 'type': 'image', 'caption': 'Product launch'}],
    [
        {'url': 'https://picsum.photos/id/201/800/500', 'type': 'image', 'caption': 'Day 1'},
        {'url': 'https://picsum.photos/id/202/800/500', 'type': 'image', 'caption': 'Day 2'},
    ],
    [
        {'url': 'https://picsum.photos/id/250/800/500', 'type': 'image', 'caption': 'Meeting'},
        {'url': 'https://picsum.photos/id/251/800/500', 'type': 'image', 'caption': 'Networking'},
        {'url': 'https://picsum.photos/id/252/800/500', 'type': 'image', 'caption': 'Wrap-up'},
    ],
]

LIFE_PHOTOS = [
    [{'url': 'https://picsum.photos/id/10/800/600',  'type': 'image', 'caption': 'Weekend vibes'}],
    [{'url': 'https://picsum.photos/id/26/800/600',  'type': 'image', 'caption': 'Morning run'}],
    [{'url': 'https://picsum.photos/id/42/800/600',  'type': 'image', 'caption': 'Lake Victoria'}],
    [{'url': 'https://picsum.photos/id/57/800/600',  'type': 'image', 'caption': 'Kampala skyline'}],
    [{'url': 'https://picsum.photos/id/91/800/600',  'type': 'image', 'caption': 'Coffee break'}],
    [{'url': 'https://picsum.photos/id/136/800/600', 'type': 'image', 'caption': 'Brunch 🍳'}],
    [{'url': 'https://picsum.photos/id/219/800/600', 'type': 'image', 'caption': 'Sunset in Jinja'}],
    [
        {'url': 'https://picsum.photos/id/305/800/600', 'type': 'image', 'caption': ''},
        {'url': 'https://picsum.photos/id/306/800/600', 'type': 'image', 'caption': ''},
    ],
]


# ── Post content ──────────────────────────────────────────────────────────────

PROFESSIONAL_TEXT_POSTS = [
    ("🚀 Excited to announce that I've joined Andela as a Senior Software Engineer! "
     "After 3 years building products for East Africa's growing tech ecosystem, "
     "this feels like the right next step. Grateful for every mentor and colleague "
     "who believed in this journey. Here's to the next chapter! 🙌",
     ['career', 'tech', 'andela', 'kampala']),

    ("Hot take: Most Ugandan startups fail not because of product but because of "
     "distribution. We obsess over building the perfect feature set while completely "
     "ignoring go-to-market strategy. What do you think — product or distribution first?",
     ['startups', 'uganda', 'entrepreneurship']),

    ("Just finished leading a 3-day Design Sprint for a HealthTech client. "
     "The energy in the room when the team aligned on a single solution after days "
     "of divergent thinking — there's nothing quite like it. Design thinking works. 🎨",
     ['design', 'designthinking', 'healthtech']),

    ("Mobile money is the backbone of Uganda's digital economy. "
     "MTN MoMo alone processes more transactions per day than most East African banks combined. "
     "Yet we're still treating it as a 'feature' rather than infrastructure. "
     "The real fintech opportunity is in the layer above mobile money, not replacing it.",
     ['fintech', 'mobilemoney', 'mtn', 'uganda']),

    ("I've been mentoring 4 junior developers for the past 6 months. "
     "Here's what I've learned: the fastest way to grow isn't more courses — "
     "it's shipping real things and handling feedback. Code review is the best classroom. 💻",
     ['mentorship', 'softwareengineering', 'careeradvice']),

    ("Attended the Uganda FinTech Summit yesterday. Key takeaway: "
     "financial inclusion in Uganda is still largely a rural problem. "
     "67% of the population remains unbanked, but 84% have mobile phones. "
     "The gap is not technology — it's trust and education. 📊",
     ['fintech', 'financialinclusion', 'uganda']),

    ("Something I wish I knew earlier in my career: "
     "Your network is your net worth. Not in a transactional way — "
     "but genuine relationships built over years become the foundation "
     "of everything: jobs, collaborations, referrals, mental health. "
     "Invest in people, not just skills.",
     ['networking', 'career', 'professional']),

    ("We just hit 10,000 active users on our agritech platform! 🌾 "
     "Started in a small office in Ntinda with 3 people and a dream. "
     "Two years later we're helping over 2,000 smallholder farmers "
     "access better market prices. This is what impact looks like. 🙏",
     ['agritech', 'impact', 'startup', 'uganda']),

    ("Looking for talented data scientists in Kampala. "
     "Skills needed: Python, SQL, ML basics, storytelling with data. "
     "The role involves building predictive models for credit risk in the East African market. "
     "DM me or drop your CV in the comments. Remote-friendly! 📈",
     ['hiring', 'datascience', 'kampala', 'remote']),

    ("Reflection after 5 years in product management: "
     "The best PMs I've worked with aren't the ones with the best frameworks — "
     "they're the ones who listen most carefully and hold their opinions lightly. "
     "Ego is the biggest product killer. 🎯",
     ['product', 'productmanagement', 'career']),

    ("Our team just deployed a real-time crop disease detection model "
     "using satellite imagery and mobile phone photos. "
     "Farmers in Luwero can now get diagnosis results in under 30 seconds. "
     "This is what applied AI looks like in Africa 🌍",
     ['ai', 'agritech', 'machinelearning', 'africa']),

    ("Just got back from a leadership conference in Nairobi. "
     "One thing struck me: Ugandan professionals are incredibly talented "
     "but often undersell themselves on the regional stage. "
     "We need more confidence in our own capabilities. 🦁",
     ['leadership', 'uganda', 'africa', 'conference']),

    ("3 years ago I was a recent Makerere graduate with no job and no idea what to do. "
     "Today I manage a team of 8 engineers building infrastructure for Uganda's public sector. "
     "The journey is never linear but it is always forward. Keep going. ❤️",
     ['career', 'makerere', 'inspiration', 'publictech']),

    ("Unpopular opinion: Most 'digital transformation' projects in Uganda fail "
     "because they copy Western solutions without adapting for African contexts. "
     "Intermittent power, feature phones, low bandwidth — these are constraints, "
     "not excuses. Design for reality. 🔌",
     ['digitaltransformation', 'africa', 'techforchange']),

    ("Just completed my AWS Solutions Architect certification! 🏆 "
     "If you're in East Africa and thinking about cloud infrastructure, "
     "the opportunities are enormous. The government alone is spending $200M+ "
     "on cloud migration over the next 3 years.",
     ['aws', 'cloud', 'certification', 'uganda']),

    ("The most underrated skill in tech? Writing clearly. "
     "Being able to explain a complex system in plain language is worth "
     "more than knowing 10 different frameworks. "
     "Write more. Document more. Communicate more. 📝",
     ['writing', 'communication', 'softskills']),

    ("Healthcare workers in Uganda are overstretched. "
     "The nurse-to-patient ratio in public hospitals is 1:64. "
     "We're building a triage tool that helps nurses prioritise cases faster. "
     "It's not glamorous AI — but it might save lives. 💉",
     ['healthtech', 'uganda', 'impact', 'ai']),

    ("Spent the morning teaching coding to 40 S4 students at Mengo Senior School. "
     "These kids are sharp, curious, and hungry. "
     "If we invest in STEM education now, Uganda will have a serious tech talent pipeline "
     "in 10 years. This is the work that matters. 🏫",
     ['education', 'stem', 'coding', 'kampala']),

    ("Big wins today: closed our Series A round 🎉 "
     "We're raising UGX 3.5B to expand to Rwanda and Tanzania. "
     "Incredibly grateful to our investors who believed in a pan-African vision "
     "from a team in Kampala. More details next week!",
     ['startup', 'fundraising', 'expansion', 'seriesa']),

    ("How I went from struggling junior dev to tech lead in 4 years:\n\n"
     "1. Said yes to hard problems\n"
     "2. Found mentors who were brutally honest\n"
     "3. Built things in public\n"
     "4. Learned to communicate, not just code\n"
     "5. Took ownership of outcomes, not just tasks\n\n"
     "The technical skills matter but they're table stakes. 🚀",
     ['career', 'techleader', 'softwareengineering']),

    ("Remote work in Uganda: the infrastructure is getting there. "
     "Starlink has changed the game for anyone outside Kampala. "
     "I'm currently writing this from my family's farm in Mbale "
     "with 80Mbps download speed. The future is distributed. 📡",
     ['remotework', 'starlink', 'mbale', 'future']),

    ("Human-centred design isn't a luxury — it's a necessity for African tech. "
     "We built a payments app that required 12-step onboarding. "
     "Our conversion rate was 3%. We redesigned it to 4 steps. "
     "Conversion jumped to 34%. People will tell you what they need if you listen. 👂",
     ['ux', 'design', 'fintech', 'conversion']),

    ("Proud to have been part of the team that built Uganda's national immunisation "
     "tracking system. 4.2M children registered in the first year. "
     "Technology for public good is the most meaningful work I've done. 💚",
     ['govtech', 'healthcare', 'impact', 'uganda']),

    ("Every engineer in East Africa should understand mobile money APIs. "
     "MTN, Airtel, and M-Pesa together cover 98% of the use cases you'll encounter. "
     "I'm writing a comprehensive guide — follow me to get notified when it drops. 📚",
     ['mobilemoney', 'api', 'developer', 'eastafrica']),

    ("Just finished reading 'The Mom Test' by Rob Fitzpatrick. "
     "If you're building anything — a startup, a feature, even a presentation — "
     "read this book. The insight: people won't tell you your idea is bad. "
     "Ask about their life, not your idea. 💡",
     ['reading', 'startups', 'productdesign', 'books']),

    ("5 lessons from building in Uganda's market:\n"
     "1. Cash is still king outside Kampala\n"
     "2. Referrals convert 10x better than ads\n"
     "3. WhatsApp is your distribution channel\n"
     "4. Feature phones can't be ignored\n"
     "5. Trust takes time — build it through consistency\n\n"
     "Learn the market first. Ship second. 🇺🇬",
     ['startups', 'ugandatech', 'market', 'distribution']),

    ("Our SACCO just onboarded 200 new members using our mobile platform! 🎊 "
     "Previously it took 3 visits to the office and weeks of paperwork. "
     "Now it's a 10-minute digital process. "
     "Financial inclusion, one feature at a time.",
     ['sacco', 'fintech', 'financialinclusion', 'uganda']),

    ("I've hired 30+ people in my career. "
     "The biggest mistake I see candidates make: not asking questions. "
     "An interview is a two-way conversation. "
     "If you don't ask thoughtful questions, I assume you don't really want the role. "
     "Come prepared. 🎯",
     ['hiring', 'career', 'interview', 'advice']),

    ("Agribusiness is Uganda's biggest GDP sector and most underserved digitally. "
     "Coffee farmers in Mt Elgon still use pen-and-paper record keeping. "
     "There's a $2B digital transformation opportunity hiding in the hills. 🌿",
     ['agribusiness', 'digitaltransformation', 'uganda', 'opportunity']),

    ("On being a woman in tech in Uganda:\n\n"
     "It's harder. The bias is real but mostly unconscious. "
     "The best thing allies can do is amplify our voices in rooms we're not in. "
     "The best thing we can do is show up anyway and build anyway. 🔥",
     ['womenintech', 'diversity', 'inclusion', 'uganda']),
]

DATING_TEXT_POSTS = [
    ("Kampala sunset hits different when you're watching it from Kololo Hill. "
     "Anyone else find that golden hour makes everything feel possible? ✨",
     ['kampala', 'sunset', 'life']),

    ("Things I'm looking for in a partner:\n"
     "• Laughs at their own jokes before finishing them\n"
     "• Has a favourite book and an opinion about it\n"
     "• Comfortable with silence\n"
     "• Knows what they want to eat (I'm kidding... mostly)\n"
     "• Genuinely curious about the world 🌍",
     ['dating', 'partner', 'vibes']),

    ("Coffee date or dinner date for a first meeting? "
     "I'm a strong coffee-date advocate — lower stakes, easier to leave, "
     "and if it goes well you can extend. Drop your vote below 👇",
     ['dating', 'firstdate', 'kampala']),

    ("I think the most attractive quality in a person is intellectual curiosity. "
     "Tell me what you're obsessed with learning right now and I'll tell you "
     "everything about mine. What's on your mind? 💭",
     ['connection', 'intellectual', 'curious']),

    ("Hot take: the best dates in Kampala aren't at fancy restaurants. "
     "They're at Owino Market, a rolex stall, or a boda-boda ride "
     "where you're forced to hold on and talk loud. Real connection > Instagram settings.",
     ['kampala', 'dating', 'authentic']),

    ("Confessions of an introvert on a dating app:\n"
     "I write things I'd never say out loud, then panic when asked to meet. "
     "Working on it though. Baby steps. 😅",
     ['introvert', 'dating', 'growth']),

    ("What's something you do every morning that makes your day better? "
     "Mine: 30 minutes of reading before I touch my phone. "
     "It's the only time I feel genuinely present. 📖",
     ['morningroutine', 'selfcare', 'mindfulness']),

    ("Honest question: do you think long-distance can actually work in Uganda "
     "when you're both in different cities — like Kampala and Gulu? "
     "The 6-hour drive changes the math completely. 🚌",
     ['longdistance', 'relationships', 'uganda']),

    ("Green flag: someone who asks follow-up questions in a conversation. "
     "It means they're actually listening. "
     "Most rare skill in 2025. 👂",
     ['greenflags', 'dating', 'listening']),

    ("I speak Luganda, English, and enough Runyankole to order rolex and get directions. "
     "Working on Swahili. Looking for someone who finds multilingualism charming "
     "rather than showing off. 😄",
     ['uganda', 'languages', 'culture']),

    ("Favourite thing about Kampala nights: the energy shifts completely after 8pm. "
     "The city relaxes. The music gets louder. People become themselves. "
     "If you've never walked Old Kampala Road at night, you haven't met Kampala yet. 🌙",
     ['kampala', 'nightlife', 'city']),

    ("Pet peeve: people who are on their phone the entire time during a date. "
     "Like, I competed with the algorithm for your attention and lost before we even ordered. 📵",
     ['petpeeve', 'dating', 'presence']),

    ("Boda-boda rides are honestly the most honest form of intimacy in Uganda. "
     "You hold a stranger's shoulders, they take you somewhere in 8 minutes, "
     "and you never meet again. Beautiful and chaotic. 🏍️",
     ['kampala', 'bodaboda', 'life']),

    ("Things I find irresistible:\n"
     "- Someone passionate about their work\n"
     "- Kindness to waiters and boda riders\n"
     "- Knowing your way around a kitchen\n"
     "- Being genuinely funny (not try-hard funny)\n"
     "- Having goals and actually chasing them",
     ['attraction', 'dating', 'values']),

    ("Is it just me or does Ugandan rolex culture need to come to every country? "
     "Eggs, veggies, chapati, rolled up. 500 shillings. Perfect meal. "
     "I judge relationships by rolex compatibility. 🫔",
     ['uganda', 'rolex', 'food', 'culture']),
]

BOTH_TEXT_POSTS = [
    ("Grateful for this city. Kampala is chaotic, yes — "
     "but it's also alive in a way that no other place I've visited has matched. "
     "The energy, the hustle, the warmth of people. Home. 🏙️",
     ['kampala', 'home', 'gratitude']),

    ("2025 goals update (mid-year check-in):\n"
     "✅ Learn piano — started in January, can play one song\n"
     "✅ Read 24 books — on book 19\n"
     "⏳ Run a half marathon — signed up for October\n"
     "❌ Learn to cook — failed spectacularly\n\n"
     "Progress, not perfection. 🎵",
     ['goals', 'growth', 'selfimprovement']),

    ("Went hiking in Bwindi last weekend. "
     "If you've never trekked through impenetrable forest to find mountain gorillas, "
     "put it on your bucket list right now. The privilege of that encounter "
     "stays with you for life. 🦍",
     ['travel', 'bwindi', 'gorillas', 'uganda']),

    ("Here's a thought I keep coming back to: "
     "The best version of yourself is not some future state. "
     "It's the current version that's honest, curious, and kind — even when it's hard. "
     "Stop waiting to 'arrive'. You're already there.",
     ['mindset', 'growth', 'selfawareness']),

    ("Turns out the best therapy is a 2-hour drive upcountry with good music, "
     "nothing to do, and nowhere to be. "
     "Uganda's countryside should be prescribed by doctors. 🌿",
     ['ugandalife', 'mentalhealth', 'nature']),
]

ARTICLE_POSTS = [
    (
        "The State of Software Engineering in Uganda: 2025",
        "Uganda's tech ecosystem has grown from a handful of IT shops in 2010 "
        "to over 400 registered technology companies today. Kampala is the regional hub, "
        "but increasingly we're seeing talent and startups emerge from Mbarara, Gulu, and Mbale.\n\n"
        "The talent supply has grown faster than local demand, creating a fascinating dynamic: "
        "Ugandan engineers are increasingly working for international companies remotely "
        "while building local startups on the side.\n\n"
        "Key trends:\n"
        "1. Mobile-first development remains dominant\n"
        "2. Cloud adoption is accelerating post-COVID\n"
        "3. AI/ML skills are in shortage but growing fast\n"
        "4. Government projects are the largest employer of local tech talent\n\n"
        "The ecosystem is maturing, but funding, mentorship, and connectivity "
        "outside Kampala remain the biggest challenges.",
        ['tech', 'uganda', 'softwaredevelopment', 'eastafrica'],
    ),
    (
        "Why Financial Inclusion in Uganda Requires a Different Playbook",
        "When Western fintech companies enter Uganda, they often bring assumptions "
        "baked in Silicon Valley or London. Those assumptions break fast.\n\n"
        "Uganda's financial landscape is characterised by:\n"
        "• 14 million mobile money accounts vs. 4 million bank accounts\n"
        "• 67% of the population in rural areas where cash dominates\n"
        "• Seasonal income patterns tied to agriculture\n"
        "• Deep family financial obligations (school fees, medical, weddings)\n\n"
        "The solutions that work here are not scaled-down versions of Western products. "
        "They are built from first principles around trust, community, and the specific "
        "rhythms of Ugandan economic life.\n\n"
        "Mobile money is not a stepping stone to 'real' banking — "
        "it IS the infrastructure. Build on it.",
        ['fintech', 'financialinclusion', 'uganda', 'mobilemoney'],
    ),
    (
        "Building a Product Team from Scratch in East Africa",
        "When I joined as Head of Product two years ago, "
        "there was no product function. Just engineers building what sales asked for.\n\n"
        "Here's how we went from 0 to a 6-person product team in 18 months:\n\n"
        "**Phase 1: Earn trust (months 1-3)**\n"
        "Don't come in with frameworks. Understand the business first. "
        "Shadow sales. Read support tickets. Meet users.\n\n"
        "**Phase 2: Create clarity (months 4-8)**\n"
        "Write the first product strategy. Define success metrics. "
        "Stop measuring output, start measuring outcomes.\n\n"
        "**Phase 3: Build the team (months 9-18)**\n"
        "Hire for curiosity and user empathy above technical skills. "
        "East Africa has an abundance of smart, hungry graduates — "
        "you need to invest in developing them.\n\n"
        "It's hard, messy work. And completely worth it.",
        ['product', 'leadership', 'team', 'eastafrica'],
    ),
]

POLLS = [
    (
        "What's the biggest challenge for tech startups in Uganda right now?",
        ["Access to funding", "Finding technical talent", "Market size / distribution", "Government regulation"],
        ['startups', 'uganda', 'tech'],
    ),
    (
        "Which technology will have the most impact on Uganda's economy in the next 5 years?",
        ["AI / Machine Learning", "Mobile Money & FinTech", "Solar Energy & Clean Tech", "Agri-Tech"],
        ['technology', 'uganda', 'future'],
    ),
    (
        "How do you prefer to work?",
        ["Fully remote", "Hybrid (2-3 days office)", "Fully in-office", "I move around — depends on project"],
        ['remotework', 'worklife', 'professional'],
    ),
    (
        "What's your go-to first date activity in Kampala?",
        ["Coffee at a café", "Rooftop bar / drinks", "Outdoor activity (hiking, cycling)", "Restaurant dinner"],
        ['dating', 'kampala', 'firstdate'],
    ),
    (
        "Best way to grow professionally in Uganda?",
        ["Formal mentorship programme", "Side projects / building things", "Attending meetups/conferences", "LinkedIn + online communities"],
        ['career', 'professional', 'growth'],
    ),
    (
        "Is remote work actually productive?",
        ["Yes — more productive than office", "About the same", "Less productive but better work-life balance", "Depends on the role / person"],
        ['remotework', 'productivity'],
    ),
    (
        "What time of day are you most productive?",
        ["Early morning (5am–9am)", "Morning (9am–12pm)", "Afternoon (1pm–5pm)", "Night (8pm+)"],
        ['productivity', 'workstyle'],
    ),
    (
        "Dating style: what describes you best?",
        ["I know what I want from day one", "I prefer taking it slow and seeing where it goes", "I'm exploring — not putting labels on things", "Currently focused on myself"],
        ['dating', 'relationships', 'style'],
    ),
]

COMMENT_BODIES = [
    "This is such an important perspective — thanks for sharing!",
    "Fully agree with this. We need more conversations like this in Uganda. 🙌",
    "Interesting take. I'd push back slightly on point 3 though...",
    "This hits home. Went through exactly this in my first year. Solidarity! ❤️",
    "Bookmarking this. Sharing with my team tomorrow.",
    "The point about trust is 🔑. You can't shortcut it.",
    "So well articulated. This should be on the curriculum at Makerere.",
    "Have you written more about this? Would love to read a longer piece.",
    "The mobile money insight is fire 🔥 — been saying this for 2 years.",
    "Great post! I'd add that mentorship quality matters as much as quantity.",
    "This deserves a repost. Real talk from someone who's done the work.",
    "Congrats on the milestone! Well deserved 🎉",
    "The distribution point is something I keep seeing founders ignore. Painful to watch.",
    "Remote work + Starlink has genuinely changed my life. Based in Lira now, working for a London company.",
    "The boda ride analogy 😂 So accurate.",
    "Thank you for the vulnerable share. It matters.",
    "Needed to see this today. Thank you.",
    "Which café in Kampala are you referring to? Need the recommendation 😄",
    "The rolex rating system is the only one that matters tbh.",
    "This is the kind of content that makes LinkUp worth having.",
    "Counterpoint: sometimes the fancy restaurant IS the vibe. Set the tone right 😄",
    "Following for more of this honest content.",
    "The 'design for reality' line should be on every Ugandan tech company's wall.",
    "I wish I'd had this advice 5 years ago.",
    "Saved. Sharing this with every founder I know.",
    "The Series A news!! Congrats! 🎉 Can't wait to see you expand.",
    "MTN MoMo stat is wild. We underestimate the scale daily.",
    "This is the quiet revolution happening in Uganda and nobody's writing about it.",
    "Been following your journey. Incredible growth. Keep going! 💪",
    "The 'ego is the biggest product killer' line just hit different.",
]


def seed_posts():
    with app.app_context():
        # Fetch all accounts
        accounts = Account.query.filter_by(deleted_at=None).all()
        if not accounts:
            print("No accounts found. Run seed.py first.")
            return

        account_ids = [a.id for a in accounts]
        print(f"Found {len(accounts)} accounts. Creating posts...")

        created_posts = []

        # ── 1. Professional text posts (one per entry, cycling through accounts) ────
        for i, (body, tags) in enumerate(PROFESSIONAL_TEXT_POSTS):
            author_id = account_ids[i % len(account_ids)]
            ts = rng_dt(days_ago_max=55, days_ago_min=1)
            p = Post(
                id=uid(), author_id=author_id,
                mode='professional', post_type='text',
                body=body, audience='public',
                tags=tags,
                likes_count=random.randint(5, 180),
                comments_count=random.randint(2, 40),
                views_count=random.randint(80, 2000),
                is_featured=1 if i < 3 else 0,
                created_at=ts, updated_at=ts,
            )
            db.session.add(p)
            created_posts.append(p)

        # ── 2. Dating text posts ─────────────────────────────────────────────
        for i, (body, tags) in enumerate(DATING_TEXT_POSTS):
            author_id = account_ids[i % len(account_ids)]
            ts = rng_dt(days_ago_max=50, days_ago_min=1)
            p = Post(
                id=uid(), author_id=author_id,
                mode='dating', post_type='text',
                body=body, audience='public',
                tags=tags,
                likes_count=random.randint(3, 90),
                comments_count=random.randint(1, 20),
                views_count=random.randint(40, 800),
                created_at=ts, updated_at=ts,
            )
            db.session.add(p)
            created_posts.append(p)

        # ── 3. Both-mode life posts ──────────────────────────────────────────
        for i, (body, tags) in enumerate(BOTH_TEXT_POSTS):
            author_id = account_ids[(i + 7) % len(account_ids)]
            ts = rng_dt(days_ago_max=40, days_ago_min=1)
            p = Post(
                id=uid(), author_id=author_id,
                mode='both', post_type='text',
                body=body, audience='public',
                tags=tags,
                likes_count=random.randint(10, 120),
                comments_count=random.randint(3, 25),
                views_count=random.randint(100, 1500),
                created_at=ts, updated_at=ts,
            )
            db.session.add(p)
            created_posts.append(p)

        # ── 4. Photo posts — professional ───────────────────────────────────
        professional_photo_captions = [
            "Team photo from our product sprint last week! Proud of this crew. 💪",
            "Speaking at the Kampala Tech Meetup yesterday. Great energy from the room!",
            "Our new office is finally ready. Three months of planning, worth every minute. 🏢",
            "Representing Uganda at the East Africa Startup Summit in Nairobi 🇺🇬🤝🇰🇪",
            "Workshop day with the Makerere innovation lab. The students' ideas blew us away.",
            "Product demo day. 3 months of building. This is what it looks like. 🚀",
            "Final day of our design bootcamp. 40 participants, 8 prototypes, 1 winner. 🎨",
            "Closing our Series A is something I'll never forget. Thank you, team. 🥂",
            "Site visit to the Mbarara hub. Talent everywhere outside Kampala. 🌍",
            "Partnered with NITA-U on our digital ID pilot. This is what public-private looks like.",
        ]
        for i, caption in enumerate(professional_photo_captions):
            author_id = account_ids[(i + 2) % len(account_ids)]
            ts = rng_dt(days_ago_max=45, days_ago_min=1)
            media = TECH_PHOTOS[i % len(TECH_PHOTOS)]
            # Update caption if media has empty one
            media_with_caption = [dict(m, caption=caption if not m['caption'] else m['caption']) for m in media]
            p = Post(
                id=uid(), author_id=author_id,
                mode='professional', post_type='photo',
                body=caption, media=media_with_caption,
                audience='public',
                tags=['professional', 'team', 'kampala'],
                likes_count=random.randint(15, 200),
                comments_count=random.randint(3, 50),
                views_count=random.randint(150, 2500),
                created_at=ts, updated_at=ts,
            )
            db.session.add(p)
            created_posts.append(p)

        # ── 5. Photo posts — dating / life ───────────────────────────────────
        dating_photo_captions = [
            "Weekend escape to Jinja. The Nile never disappoints. 🌊",
            "Brunch in Kololo with my favourite people. Life is good. 🍳",
            "Hiking Sipi Falls solo for the first time. 10/10 recommend. 🏔️",
            "Home-cooked Sunday meal. Proud of this one. 🫕",
            "My happy place. 🌿",
            "Golden hour hits different when you've had a good week. ✨",
        ]
        for i, caption in enumerate(dating_photo_captions):
            author_id = account_ids[(i + 5) % len(account_ids)]
            ts = rng_dt(days_ago_max=35, days_ago_min=1)
            media = LIFE_PHOTOS[i % len(LIFE_PHOTOS)]
            p = Post(
                id=uid(), author_id=author_id,
                mode='dating', post_type='photo',
                body=caption, media=media,
                audience='public',
                tags=['lifestyle', 'uganda', 'life'],
                likes_count=random.randint(8, 120),
                comments_count=random.randint(2, 30),
                views_count=random.randint(60, 900),
                created_at=ts, updated_at=ts,
            )
            db.session.add(p)
            created_posts.append(p)

        # ── 6. Article posts ──────────────────────────────────────────────────
        for i, (title, body, tags) in enumerate(ARTICLE_POSTS):
            author_id = account_ids[(i + 1) % len(account_ids)]
            ts = rng_dt(days_ago_max=30, days_ago_min=2)
            p = Post(
                id=uid(), author_id=author_id,
                mode='professional', post_type='article',
                title=title, body=body,
                audience='public', tags=tags,
                likes_count=random.randint(25, 250),
                comments_count=random.randint(5, 60),
                views_count=random.randint(300, 5000),
                created_at=ts, updated_at=ts,
            )
            db.session.add(p)
            created_posts.append(p)

        # ── 7. Poll posts ─────────────────────────────────────────────────────
        for i, (question, options, tags) in enumerate(POLLS):
            author_id = account_ids[(i + 3) % len(account_ids)]
            ts = rng_dt(days_ago_max=20, days_ago_min=1)
            from datetime import timedelta
            poll_options = [
                {'id': uid()[:8], 'text': opt, 'vote_count': random.randint(5, 80)}
                for opt in options
            ]
            mode = 'dating' if 'dating' in tags else 'professional'
            p = Post(
                id=uid(), author_id=author_id,
                mode=mode, post_type='poll',
                body=question,
                audience='public', tags=tags,
                poll_question=question,
                poll_options=poll_options,
                poll_ends_at=datetime.utcnow() + timedelta(days=random.randint(1, 7)),
                likes_count=random.randint(10, 60),
                comments_count=random.randint(3, 20),
                views_count=random.randint(200, 1500),
                created_at=ts, updated_at=ts,
            )
            db.session.add(p)
            created_posts.append(p)

        # ── 8. "Connections only" professional posts ──────────────────────────
        private_bodies = [
            "Had a rough week — project got cancelled after 3 months of work. "
            "Taking the weekend to reset. If anyone wants to grab coffee in Kamwokya, DM me.",
            "Sharing with my network only: we're hiring 2 senior engineers internally first "
            "before going public. Referrals preferred. Python/React stack. Reach out!",
            "Bit of an imposter syndrome day. Presenting to 200 people tomorrow and I feel "
            "completely unprepared. Any advice from those who've been there?",
            "Our company might be acquired. Can't say more. Just needed to write that down somewhere.",
            "Low-key celebrating 1 year at this company. It's been hard but I've grown more "
            "than in any previous role. Sometimes the discomfort is the growth.",
        ]
        for i, body in enumerate(private_bodies):
            author_id = account_ids[(i + 4) % len(account_ids)]
            ts = rng_dt(days_ago_max=15, days_ago_min=1)
            p = Post(
                id=uid(), author_id=author_id,
                mode='professional', post_type='text',
                body=body, audience='connections',
                tags=['reflection', 'career'],
                likes_count=random.randint(3, 30),
                comments_count=random.randint(1, 10),
                views_count=random.randint(20, 200),
                created_at=ts, updated_at=ts,
            )
            db.session.add(p)
            created_posts.append(p)

        # ── 9. Additional filler text posts to reach 200 ─────────────────────
        filler = [
            ("Grateful for the LinkUp community. This platform has introduced me to "
             "5 collaborators I wouldn't have found otherwise. Keep building! 🙌",
             'professional', ['linkup', 'community', 'networking']),
            ("Morning reminder: progress over perfection. Shipped is better than perfect. "
             "What did you ship this week? 🚀", 'professional', ['productivity', 'shipping']),
            ("Anyone working on something in the climate tech space in East Africa? "
             "Looking to connect. 🌿", 'professional', ['climatetech', 'eastafrica']),
            ("The best investment I made in 2024 was a proper ergonomic chair and external monitor. "
             "Remote work quality of life went up 40%. 💻", 'professional', ['remotework', 'wfh']),
            ("Officially a year into learning French. Can now order food and get lost in Francophone Africa. "
             "Small wins. 🥐", 'both', ['learning', 'languages', 'personal']),
            ("Hot take: the most important course at Makerere Business School should be "
             "'How to actually talk to customers'. Not accounting. 😅", 'professional', ['education', 'mubs', 'startups']),
            ("Just got back from a week in Kigali. The infrastructure gap between Uganda and Rwanda "
             "is real and humbling. Friendly competition drives everyone forward. 🇷🇼",
             'professional', ['kigali', 'rwanda', 'eastafrica']),
            ("Anyone building anything interesting using the MTN MoMo sandbox? "
             "Looking to connect with devs in this space. 📲", 'professional', ['mtn', 'mobilemoney', 'api']),
            ("Something clicked today about leadership: your job is to make people around you "
             "more effective, not to be the most effective person yourself. "
             "Different skill set entirely. 🎯", 'professional', ['leadership', 'management']),
            ("It's been 500 days since I started journaling daily. "
             "The clarity it's given me is hard to describe. Recommend to everyone, especially founders.",
             'both', ['journaling', 'mentalclarity', 'habits']),
            ("Running a tech company in Uganda means managing 3 things simultaneously: "
             "building the product, building the team, and educating the market. "
             "Each one is a full-time job.", 'professional', ['startup', 'founder', 'uganda']),
            ("Our youth coding programme just graduated its third cohort — 80 students, "
             "60% female, 3 already employed. This is why we do the work. 👩‍💻",
             'professional', ['education', 'coding', 'inclusion']),
            ("The best pitch deck advice I ever got: "
             "lead with the problem, not the solution. "
             "Investors fund solutions to real problems, not clever technologies.",
             'professional', ['fundraising', 'pitch', 'startup']),
            ("UX research insight from this week: "
             "99% of users in our target market use WhatsApp daily. "
             "0% use email. We're rethinking our entire communication strategy.",
             'professional', ['ux', 'research', 'whatsapp', 'africa']),
            ("Annual reflection: what did you start this year that you're proud of? "
             "Not finished — just started. Sometimes beginning is the whole point. ✨",
             'both', ['reflection', 'growth', '2025']),
            ("Anyone know good co-working spaces in Mbarara? "
             "Spending a month there for a client project. 🏢",
             'professional', ['mbarara', 'coworking', 'uganda']),
            ("The loneliness of being a solo founder is real and nobody talks about it. "
             "Having 2 co-founders doesn't always help — sometimes all 3 of you are isolated together.",
             'professional', ['founder', 'startup', 'mentalhealth']),
            ("Celebrating 10 years in the workforce today. "
             "The 25-year-old version of me had no idea what was coming. "
             "Grateful for every stumble and every win. 🥂",
             'both', ['career', 'milestone', 'gratitude']),
            ("Open source East Africa: we need more engineers contributing to projects "
             "that solve African problems. Not just consuming open source. "
             "What are you building and sharing?",
             'professional', ['opensource', 'eastafrica', 'developers']),
            ("A thank you to every person who ever gave honest feedback on my work. "
             "It's not always comfortable but it's always valuable. "
             "Be that person for someone today.",
             'professional', ['feedback', 'growth', 'kindness']),
            ("Finding out that one of our users built a second business on top of our API "
             "without telling us. That's the ultimate product-market fit signal. 🤯",
             'professional', ['product', 'pmf', 'api', 'startup']),
            ("Spent the afternoon at the Kampala Innovation Village. "
             "The energy there is contagious. If you haven't been, go.",
             'professional', ['innovation', 'kampala', 'ecosystem']),
            ("Reminder: it's okay not to have a 5-year plan. "
             "Some of the best opportunities I've had were completely unplanned. "
             "Stay curious. Say yes to interesting things.",
             'both', ['career', 'life', 'opportunities']),
            ("Does anyone else find that the best ideas come in the shower "
             "or on a boda? Something about movement and not trying... 🚿",
             'both', ['creativity', 'ideas', 'funny']),
            ("Local founders: please talk to your customers BEFORE building. "
             "I've seen three startups this month building beautiful solutions "
             "to problems nobody actually has. Customer discovery is not optional.",
             'professional', ['startups', 'customerdiscovery', 'productdevelopment']),
            ("Trying to explain Ugandan time to a Swiss investor during a 9am call. "
             "He had already sent 3 WhatsApp messages by 8:57am. 😭 Cultural translation is real.",
             'professional', ['culture', 'business', 'startup', 'humour']),
            ("The most impactful thing any manager ever did for me: "
             "protected my time from unnecessary meetings so I could do deep work. "
             "Simple. Powerful. Rare.",
             'professional', ['management', 'deepwork', 'meetings']),
            ("Solar panel installed! 🌞 Power cuts will no longer derail my standup calls. "
             "If you're working from home in Kampala, this is the best investment you'll make.",
             'both', ['solar', 'remotework', 'kampala', 'life']),
            ("Hiring update: we got 230 applications for 2 roles. "
             "The talent in Uganda is extraordinary. "
             "The real challenge is building the infrastructure to support them.",
             'professional', ['hiring', 'talent', 'uganda']),
            ("To the young person reading this from upcountry who thinks "
             "tech is only for people in Kampala: it isn't. "
             "I'm living proof. Started in Gulu, now building for the world. 💪",
             'professional', ['inspiration', 'inclusion', 'gulu', 'tech']),
            ("Random thought: the most successful people I know are consistently curious. "
             "Not smart by exam standards — curious by nature. "
             "That appetite to understand is everything.",
             'both', ['curiosity', 'success', 'mindset']),
            ("Sharing something personal: I almost quit tech three years ago. "
             "Burnout, imposter syndrome, the whole package. "
             "This community helped me stay. Thank you.",
             'professional', ['mentalhealth', 'burnout', 'community']),
            ("Launching our new AI-powered HR tool for SMEs next month. "
             "Looking for 20 beta testers in Uganda. "
             "Free access for 6 months. Drop your email in the comments! 🤖",
             'professional', ['ai', 'hr', 'sme', 'betatesting']),
            ("The difference between a good engineer and a great one "
             "isn't the code they write — it's the decisions they don't make "
             "when they could have simplified.",
             'professional', ['engineering', 'simplicity', 'advice']),
            ("Family is coming to visit from diaspora this week. "
             "Already planning the Kampala eating tour: Nandos? Wandegeya chips? Guvnor?",
             'both', ['family', 'kampala', 'food', 'diaspora']),
            ("Officially on the board of a Uganda tech startup! "
             "Never thought I'd be here at 31. "
             "Keep your network warm. You never know where the next opportunity comes from.",
             'professional', ['board', 'startup', 'career', 'milestone']),
            ("Night markets in Kampala are underrated for networking. "
             "Less formal, better food, people are more honest. "
             "Fight me.",
             'professional', ['kampala', 'networking', 'nightlife']),
            ("Deep learning course complete ✅ "
             "Now I just need to build something useful with it. "
             "Any interesting datasets or problems in the East Africa space I should look at?",
             'professional', ['machinelearning', 'deeplearning', 'eastafrica']),
            ("Shoutout to every entrepreneur who is building in a city with load shedding, "
             "spotty internet, and a small market — and still showing up every single day. "
             "You're not at a disadvantage. You're building resilience that Silicon Valley will never have.",
             'professional', ['entrepreneurship', 'africa', 'resilience', 'founder']),
        ]

        for i, (body, mode, tags) in enumerate(filler):
            author_id = account_ids[(i + 6) % len(account_ids)]
            ts = rng_dt(days_ago_max=60, days_ago_min=1)
            p = Post(
                id=uid(), author_id=author_id,
                mode=mode, post_type='text',
                body=body, audience='public',
                tags=tags,
                likes_count=random.randint(2, 150),
                comments_count=random.randint(0, 35),
                views_count=random.randint(30, 1800),
                created_at=ts, updated_at=ts,
            )
            db.session.add(p)
            created_posts.append(p)

        db.session.commit()
        print(f"Created {len(created_posts)} posts.")

        # ── Add likes, comments, and saves across posts ───────────────────────
        print("Adding engagement data...")

        total_likes = 0
        total_comments = 0
        total_saves = 0
        used_likes = set()
        used_saves = set()

        for post in created_posts:
            # Likes (random subset of accounts)
            n_likes = min(post.likes_count, len(account_ids))
            likers = random.sample(account_ids, n_likes)
            for acct_id in likers:
                key = (post.id, acct_id)
                if key in used_likes:
                    continue
                used_likes.add(key)
                reaction = random.choice(['like', 'like', 'like', 'love', 'insightful', 'celebrate', 'support'])
                db.session.add(PostLike(
                    id=uid(), post_id=post.id, account_id=acct_id,
                    reaction_type=reaction,
                    created_at=post.created_at + timedelta(minutes=random.randint(1, 1440)),
                ))
                total_likes += 1

            # Comments
            n_comments = min(post.comments_count, 8)
            commenters = random.sample(account_ids, min(n_comments, len(account_ids)))
            parent_ids = []
            for acct_id in commenters:
                if acct_id == post.author_id and random.random() > 0.3:
                    continue
                body = random.choice(COMMENT_BODIES)
                c = PostComment(
                    id=uid(), post_id=post.id, author_id=acct_id,
                    parent_id=None, body=body,
                    likes_count=random.randint(0, 10),
                    created_at=post.created_at + timedelta(minutes=random.randint(5, 2880)),
                )
                db.session.add(c)
                parent_ids.append(c.id)
                total_comments += 1

                # 30% chance of a reply
                if random.random() < 0.3 and parent_ids:
                    reply_body = random.choice([
                        "Totally agree! Well said. 👏",
                        "Thanks for sharing this perspective.",
                        "Interesting — hadn't thought of it that way.",
                        "This is exactly the conversation we need to be having.",
                        "💯 This.",
                        "Great insight. Following for more.",
                        "Couldn't agree more!",
                        "Appreciate the honest take.",
                    ])
                    replier = random.choice([a for a in account_ids if a != acct_id])
                    reply = PostComment(
                        id=uid(), post_id=post.id, author_id=replier,
                        parent_id=c.id, body=reply_body,
                        likes_count=random.randint(0, 5),
                        created_at=c.created_at + timedelta(minutes=random.randint(2, 240)),
                    )
                    db.session.add(reply)
                    total_comments += 1

            # Saves (10% of posts)
            if random.random() < 0.1:
                savers = random.sample(account_ids, random.randint(1, 4))
                for acct_id in savers:
                    key = (post.id, acct_id)
                    if key in used_saves:
                        continue
                    used_saves.add(key)
                    db.session.add(PostSave(
                        id=uid(), post_id=post.id, account_id=acct_id,
                        created_at=post.created_at + timedelta(hours=random.randint(1, 48)),
                    ))
                    total_saves += 1

        db.session.commit()
        print(f"Added {total_likes} likes, {total_comments} comments, {total_saves} saves.")
        print(f"\n✅  Posts seed complete: {len(created_posts)} posts, {len(accounts)} users.")


if __name__ == '__main__':
    seed_posts()
