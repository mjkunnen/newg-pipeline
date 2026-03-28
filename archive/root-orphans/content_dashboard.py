"""
NEWGARMENTS — Content Ideas Dashboard
Desktop GUI Application
"""

import tkinter as tk
from tkinter import ttk, font as tkfont

# ─── COLORS ─────────────────────────────────────────────
BG = "#0a0a0a"
SURFACE = "#141414"
SURFACE_HOVER = "#1e1e1e"
SURFACE_ACTIVE = "#252525"
BORDER = "#2a2a2a"
TEXT = "#f0f0f0"
TEXT_SEC = "#888888"
TEXT_MUTED = "#555555"
COLORS = {
    "conversion": "#4ade80",
    "awareness": "#818cf8",
    "trust": "#fb923c",
    "fomo": "#f472b6",
    "engagement": "#22d3ee",
    "brand": "#a78bfa",
}
LABELS = {
    "conversion": "Conversion",
    "awareness": "Awareness",
    "trust": "Trust",
    "fomo": "FOMO",
    "engagement": "Engagement",
    "brand": "Brand",
}

# ─── DATA ───────────────────────────────────────────────
IDEAS = [
    {
        "id": 1,
        "title": "The Scale Test",
        "hook": "Your hoodie weighs this much... ours weighs this much.",
        "category": "conversion",
        "tags": ["conversion", "trust"],
        "potential": 95,
        "difficulty": 1,
        "platforms": ["TikTok", "Reels"],
        "duration": "10-15 sec",
        "why": "This is undeniable visual proof. The scale doesn't lie. It bypasses all skepticism because there's no way to fake a number on a scale. It directly addresses the #1 pain point: paying premium for thin, lightweight garbage. When Gen Z sees 340g vs 880g, the decision makes itself.",
        "psychology": "Targets the fear of getting scammed on quality. 73% of Gen Z research brands before buying because they've been burned by AliExpress-quality products marketed as premium. The scale gives them the proof they need in 10 seconds.",
        "proof": [
            ("Cole Buxton", "Pioneered fabric weight content on TikTok. Their GSM comparison videos consistently hit 100K-500K+ views. They turned 'GSM' into a mainstream streetwear term."),
            ("Generic creators", "The 'weigh my hoodie' format gets 200K-1M views regularly. One creator weighing a Zara hoodie vs a premium hoodie got 2.3M views."),
        ],
        "shots": [
            "Kitchen/postal scale on clean surface, zeroed out",
            "Hand dropping a thin fast fashion hoodie on the scale — show low number",
            "Hand dropping NEWGARMENTS hoodie on the scale — show high number (hold 2 sec)",
            "Optional: quick cut to someone wearing the hoodie, walking away",
        ],
        "text_overlay": "Stop paying premium for paper-thin hoodies.",
        "cta": "Link in bio. No restock.",
    },
    {
        "id": 2,
        "title": "The Drop Test",
        "hook": "180 GSM vs 460 GSM. You can hear the difference.",
        "category": "awareness",
        "tags": ["awareness", "trust"],
        "potential": 88,
        "difficulty": 1,
        "platforms": ["TikTok", "Reels"],
        "duration": "8-12 sec",
        "why": "Pure visual, zero words needed. Thin fabric floats like tissue. Heavyweight thuds. The contrast is visceral and the SOUND of the thud is the hook. This is the kind of content people screenshot and send to their group chat.",
        "psychology": "Taps into 'show don't tell.' Gen Z distrusts brand claims (only 26% trust brands per Edelman). But they trust their own eyes and ears. A visual comparison removes the brand's ability to lie.",
        "proof": [
            ("Fabric comparison TikToks", "Side-by-side fabric tests are a proven viral format. Simple A/B comparisons consistently outperform polished product videos."),
            ("Fashion quality creators", "Creators like @wisdm built entire audiences on 'is this worth it?' content using simple tests like this."),
        ],
        "shots": [
            "Hold thin hoodie at shoulder height — drop it (floats down slowly)",
            "Hold NEWGARMENTS hoodie at same height — drop it (thuds with weight)",
            "Optional: slow motion of the NEWGARMENTS hoodie dropping",
        ],
        "text_overlay": "180 GSM vs 460 GSM. You can hear the difference.",
        "cta": "Pin a comment with the link.",
    },
    {
        "id": 3,
        "title": "Packing ASMR",
        "hook": "Every order. Hand packed. Personal note.",
        "category": "trust",
        "tags": ["trust", "awareness", "brand"],
        "potential": 92,
        "difficulty": 1,
        "platforms": ["TikTok", "Reels", "Stories"],
        "duration": "30-45 sec",
        "why": "Packing ASMR videos consistently go viral for small brands — 500K to 2M+ views is normal. The handwritten thank-you note is your secret weapon. In a world of automated everything, a personal touch creates genuine surprise and emotional connection.",
        "psychology": "Addresses trust deficit by showing a real person behind the brand. If someone hand-packs your order and writes a personal note, the product must be good. Humanizes the brand in a way no product shot can.",
        "proof": [
            ("Broken Planet Market", "Their packing content regularly hits 500K+ views. The ASMR format builds trust and is satisfying to watch simultaneously."),
            ("Small brand TikTok", "Packing videos are the #1 recommended format for new brands. Proven track record across thousands of small businesses."),
            ("Scuffers", "Uses packing content weekly to maintain connection with their 'FF FAM' community."),
        ],
        "shots": [
            "Overhead angle: hands folding a hoodie on clean surface",
            "Wrapping in tissue paper (capture the crinkling sound)",
            "Writing the handwritten thank-you note (close-up on pen)",
            "Placing everything in branded packaging",
            "Sealing the package",
            "Optional: placing on a stack of other orders (shows demand)",
        ],
        "text_overlay": "Every order packed by hand with a personal note.",
        "cta": "None needed — pin comment with link.",
    },
    {
        "id": 4,
        "title": "NPC Fit vs Main Character Fit",
        "hook": "NPC fit vs. Main character fit",
        "category": "awareness",
        "tags": ["awareness", "engagement", "conversion"],
        "potential": 90,
        "difficulty": 2,
        "platforms": ["TikTok"],
        "duration": "12-18 sec",
        "why": "'NPC' is Gen Z's worst fashion insult. Being called basic or mid is social death. This video weaponizes their deepest fear and positions NEWGARMENTS as the cure. The transition format is native to TikTok and feels like entertainment, not an ad.",
        "psychology": "Directly triggers 'NPC anxiety' — the fear of blending in. Research shows Gen Z's #1 fashion fear is being seen as average. The before/after makes the purchase feel like a transformation, not a transaction.",
        "proof": [
            ("TikTok trend format", "NPC vs Main Character content has billions of cumulative views. Proven engagement bait because people debate in comments."),
            ("Streetwear creators", "Fit transformation videos regularly get 500K-2M views. The outfit reveal moment is inherently shareable."),
        ],
        "shots": [
            "BEFORE: generic outfit — thin hoodie, basic joggers, common shoes. Flat lighting, slouched posture.",
            "TRANSITION: quick cut or popular TikTok transition effect",
            "AFTER: full NEWGARMENTS fit. Better lighting, confident posture, heavyweight fabric visible.",
        ],
        "text_overlay": "NPC fit → Main character fit",
        "cta": "Link in bio.",
    },
    {
        "id": 5,
        "title": '"Is NEWGARMENTS a Scam?"',
        "hook": "Everyone asks if we're a scam. Fair. Let me show you everything.",
        "category": "trust",
        "tags": ["trust", "conversion"],
        "potential": 93,
        "difficulty": 2,
        "platforms": ["TikTok"],
        "duration": "45-90 sec",
        "why": "By naming the objection in the hook, you stop every skeptical scroller. Then you overwhelm with proof. This builds more trust in 60 seconds than months of polished brand content. No scam brand would make this video.",
        "psychology": "The audience actively searches '[brand] + scam' before buying. 65% have been burned by IG/TikTok brands. By addressing it first, you flip the dynamic — you look confident while competitors look like they're hiding something.",
        "proof": [
            ("Small brand strategy", "Brands that directly address 'is this a scam?' see significantly higher conversion rates than those who avoid the topic."),
            ("Broken Planet", "'Why we charge what we charge' transparency content went viral because it addressed pricing skepticism head-on."),
        ],
        "shots": [
            "Talk to camera — raw, no script. 'Everyone asks if we're a scam. Fair.'",
            "Walk through products on a table — pick each up, show weight and quality",
            "Show stitching, tags, inside construction",
            "Show packaging process — branded box, tissue paper, handwritten note",
            "Show shipping labels being printed, orders stacked",
            "End: 'We're not hiding anything. This is what we do.'",
        ],
        "text_overlay": "No AliExpress. No Gildan blanks. No BS.",
        "cta": "Judge for yourself. Link in bio.",
    },
    {
        "id": 6,
        "title": "50 Pieces. Then It's Archive.",
        "hook": "We made 50 of these. When they're gone, they're archive. No restock.",
        "category": "fomo",
        "tags": ["fomo", "conversion"],
        "potential": 87,
        "difficulty": 1,
        "platforms": ["TikTok", "Reels", "Stories"],
        "duration": "15-25 sec",
        "why": "Real scarcity stated factually — no fake countdowns, no hype language. Just a calm statement: this is how many we made, and when they're gone, they're gone. The visual of the pile being countable makes scarcity tangible.",
        "psychology": "FOMO is the #1 emotional driver for streetwear purchases. But fake scarcity destroys trust. Real scarcity stated calmly is 10x more powerful than manufactured urgency. Your audience has been burned by 'limited drops' that restocked.",
        "proof": [
            ("Corteiz", "Items sell out in hours. 'Sold Out' badges stay visible on site. Built one of the most desired streetwear brands in Europe through real scarcity."),
            ("Trapstar", "'Archive Drop' category shows past sold-out items. Visual proof that things sell out and never return creates intense FOMO."),
        ],
        "shots": [
            "Overhead shot of all pieces laid out neatly — show the limited quantity",
            "Hands picking up one piece, showing it to camera",
            "Detail shots: fabric, stitching, label",
            "Pieces being 'removed' from the pile (simulating orders)",
            "Final shot: noticeably fewer pieces remaining",
        ],
        "text_overlay": "50 pieces. Then it's gone forever.",
        "cta": "Dropping [date]. Set your alarm.",
    },
    {
        "id": 7,
        "title": "What €45 Gets You (Us vs Them)",
        "hook": "What €45 gets you from a TikTok brand vs from us.",
        "category": "conversion",
        "tags": ["conversion", "trust"],
        "potential": 91,
        "difficulty": 2,
        "platforms": ["TikTok", "Reels"],
        "duration": "20-30 sec",
        "why": "Price comparison is one of the most engaging formats on TikTok. It reframes the purchase from 'is this expensive?' to 'this is a steal.' A sad thin hoodie in a plastic mailer vs your heavyweight piece in branded packaging — the decision is obvious.",
        "psychology": "Addresses the value objection directly. Gen Z has limited budgets (€0-1500/month). Showing what their money ACTUALLY buys vs the alternative makes the rational case alongside the emotional one.",
        "proof": [
            ("TikTok comparison format", "'What $X gets you' consistently ranks among the highest-performing formats. In fashion, these drive direct conversions."),
            ("Small DTC brands", "Brands showing packaging + quality vs competitors at same price see 2-3x higher click-through rates."),
        ],
        "shots": [
            "Left: pull thin hoodie from cheap plastic mailer bag",
            "Show how light it is, thin fabric, basic single stitching",
            "Right: pull NEWGARMENTS hoodie from branded packaging with note",
            "Show weight, thickness, double stitching",
            "Optional: both on the scale for final comparison",
        ],
        "text_overlay": "Same price. Not the same hoodie.",
        "cta": "Link in bio.",
    },
    {
        "id": 8,
        "title": "Fabric Pinch Close-Up",
        "hook": "Can your hoodie do this?",
        "category": "awareness",
        "tags": ["awareness", "trust"],
        "potential": 82,
        "difficulty": 1,
        "platforms": ["TikTok", "Reels"],
        "duration": "8-12 sec",
        "why": "Macro close-ups of fabric are surprisingly mesmerizing. The thickness between two fingers is an instant quality indicator anyone can understand. Quick, punchy, incredibly easy to film.",
        "psychology": "Visual proof that bypasses all marketing language. When they see thick, dense fabric vs thin fabric that collapses — the quality argument is made without a single word. Targets the 'I can tell the difference' pride of quality-conscious buyers.",
        "proof": [
            ("Cole Buxton", "Close-up fabric texture videos are core to their strategy. They turned fabric education into aspirational content."),
            ("Streetwear TikTok", "Fabric texture and GSM content has become its own subgenre with dedicated audiences."),
        ],
        "shots": [
            "Zoom into fabric — macro or phone zoom",
            "Pinch NEWGARMENTS fabric between two fingers, pull, show thickness",
            "Do the same with a thin hoodie for contrast",
            "Optional: run fingers across surface to show texture density",
        ],
        "text_overlay": "Can your hoodie do this?",
        "cta": "Pin comment with link.",
    },
    {
        "id": 9,
        "title": "POV: No More Gildan Blanks",
        "hook": "POV: you finally find a brand that doesn't use Gildan blanks",
        "category": "conversion",
        "tags": ["conversion", "awareness"],
        "potential": 89,
        "difficulty": 2,
        "platforms": ["TikTok"],
        "duration": "15-20 sec",
        "why": "'Gildan blank' is the ultimate insult in streetwear. By naming it, you signal you understand the culture and their frustration. The POV format is native to TikTok and feels relatable, not branded.",
        "psychology": "Validates their frustration and positions NEWGARMENTS as the answer. When someone has been burned by cheap blanks multiple times, finding a brand that doesn't use them is emotional relief.",
        "proof": [
            ("Reddit r/streetwear", "'Gildan blanks' is the most common complaint about IG/TikTok brands. Shorthand for 'scam brand with logo on cheap fabric.'"),
            ("POV format", "POV videos are consistently high-performing. They feel personal and relatable, driving saves and shares."),
        ],
        "shots": [
            "Person scrolling phone looking bored (seeing mid brands)",
            "They land on NEWGARMENTS — face changes",
            "Cut to holding the hoodie — feeling weight, eyes widen",
            "Flip inside out, check stitching, nod approvingly",
            "Put it on — fit check in mirror, satisfied",
        ],
        "text_overlay": "POV: you finally find a brand that doesn't use Gildan blanks",
        "cta": "Link in bio.",
    },
    {
        "id": 10,
        "title": "Rate This Fit 1-10",
        "hook": "Rate this fit 1-10. Be honest.",
        "category": "engagement",
        "tags": ["engagement", "awareness"],
        "potential": 78,
        "difficulty": 1,
        "platforms": ["TikTok", "Reels", "Feed"],
        "duration": "8-12 sec",
        "why": "Pure engagement bait. People LOVE giving opinions. Comments flood in with ratings, debates start, algorithm pushes the video. Simplest content to make, drives reach through raw engagement numbers.",
        "psychology": "Taps into fit check culture. Asking for a rating gives permission to engage. The debate in comments drives algorithmic reach. Even negative comments help.",
        "proof": [
            ("Streetwear TikTok", "'Rate my fit' has billions of cumulative hashtag views. Works for every brand size."),
            ("Universal format", "Rating formats consistently outperform in comment counts, which directly boosts distribution."),
        ],
        "shots": [
            "Full outfit flat lay OR mirror fit check",
            "Hold for a few seconds so people can see the outfit",
        ],
        "text_overlay": "Rate this fit 1-10",
        "cta": "None — the comments are the goal.",
    },
    {
        "id": 11,
        "title": "The Inside-Out Flip",
        "hook": "If a brand won't show you the inside, there's a reason.",
        "category": "trust",
        "tags": ["trust", "awareness"],
        "potential": 85,
        "difficulty": 1,
        "platforms": ["TikTok", "Reels"],
        "duration": "10-15 sec",
        "why": "Flipping inside out is the universal quality check. Gen Z knows this. Doing it confidently on camera signals you have nothing to hide. The hook implies competitors ARE hiding something.",
        "psychology": "Positions you as transparent when others aren't. Gen Z's default is distrust — this directly addresses it by showing what most brands avoid showing.",
        "proof": [
            ("r/streetwear", "'Flip it inside out' is standard advice. Showing this on TikTok signals you know the culture."),
            ("Cole Buxton", "Regularly features inside-out shots showing construction quality as a trust signal."),
        ],
        "shots": [
            "Lay the hoodie flat",
            "Grab hem and flip inside out toward camera in one smooth motion",
            "Show inner fleece up close",
            "Show seam finishing — how clean and reinforced it is",
            "Run fingers along the stitching",
        ],
        "text_overlay": "If a brand won't show you the inside, there's a reason.",
        "cta": "We show everything. Link in bio.",
    },
    {
        "id": 12,
        "title": "The Crumple & Release",
        "hook": "Cheap fabric stays crushed. Heavyweight recovers.",
        "category": "awareness",
        "tags": ["awareness", "trust"],
        "potential": 80,
        "difficulty": 1,
        "platforms": ["TikTok", "Reels"],
        "duration": "8-12 sec",
        "why": "Quick, visual, impossible to fake. Heavyweight springs back, cheap stays wrinkled. Satisfying to watch, makes people wonder about their own hoodies.",
        "psychology": "Creates 'test it yourself' urge. After watching, viewers crumple their own hoodie — when it stays wrinkled, they think of NEWGARMENTS. You're planting a quality standard in their mind.",
        "proof": [
            ("Fabric test videos", "Simple A/B tests are proven. The crumple test is used by quality accounts and always gets strong engagement."),
        ],
        "shots": [
            "Ball up thin hoodie — release — stays wrinkled and flat",
            "Ball up NEWGARMENTS hoodie — release — springs back, holds structure",
            "Optional: slow motion of fabric recovering",
        ],
        "text_overlay": "Cheap fabric stays crushed. Heavyweight recovers.",
        "cta": "Try it with yours.",
    },
    {
        "id": 13,
        "title": '"Where\'d You Get That?"',
        "hook": "3 people asked me where I got this today.",
        "category": "conversion",
        "tags": ["conversion", "brand"],
        "potential": 86,
        "difficulty": 2,
        "platforms": ["TikTok", "Reels"],
        "duration": "15-20 sec",
        "why": "'Where did you get that?' is the ultimate compliment for this audience. It means you're wearing something rare and interesting. This sells the FEELING of wearing NEWGARMENTS.",
        "psychology": "Hits the #1 desire: peer recognition without trying. This emotional trigger is more powerful than any spec or feature.",
        "proof": [
            ("Corteiz", "Built entirely on the 'if you know, you know' dynamic. The 'where'd you get that?' moment drives word-of-mouth."),
            ("Streetwear culture", "Compliment-driven content performs well because it provides social proof through real-world validation."),
        ],
        "shots": [
            "Person talking to camera casually",
            "Quick cut montage showing piece from different angles",
            "Close-up on fabric detail while talking",
            "End on confident walk-away",
        ],
        "text_overlay": "They didn't know the brand either. That's the point.",
        "cta": "NEWGARMENTS. Link in bio.",
    },
    {
        "id": 14,
        "title": "Red Flags When Buying Streetwear",
        "hook": "Red flags to look for before buying from any streetwear brand.",
        "category": "trust",
        "tags": ["trust", "awareness", "engagement"],
        "potential": 88,
        "difficulty": 2,
        "platforms": ["TikTok"],
        "duration": "30-45 sec",
        "why": "Educational content that positions you as the honest insider. By teaching them what to look for, you implicitly position NEWGARMENTS as the brand that passes every test.",
        "psychology": "Gen Z values brands that educate rather than sell. When you help them avoid bad purchases, you build trust and authority. They'll come back because you treated them like smart people.",
        "proof": [
            ("Educational TikTok", "'Red flag' content gets high saves — viewers bookmark for future reference. Saves are the most valuable engagement signal."),
            ("Reddit r/streetwear", "'How to tell if a brand is legit' threads are among the most upvoted. Massive demand for this info."),
        ],
        "shots": [
            "Talk to camera or text-on-screen format",
            "Red flag 1: 'They're ALWAYS on sale'",
            "Red flag 2: 'No fabric specs on product page'",
            "Red flag 3: 'Stock photos, no real product shots'",
            "Red flag 4: 'No reviews or only 5-star reviews'",
            "Red flag 5: 'They say limited but keep restocking'",
            "End: 'Check these before you spend your money anywhere.'",
        ],
        "text_overlay": "Save this before your next purchase.",
        "cta": "We pass all 5. Check for yourself. Link in bio.",
    },
    {
        "id": 15,
        "title": "Sold Out Recap",
        "hook": "That was fast.",
        "category": "fomo",
        "tags": ["fomo", "brand"],
        "potential": 84,
        "difficulty": 1,
        "platforms": ["TikTok", "Reels", "Stories"],
        "duration": "10-15 sec",
        "why": "Post AFTER a drop sells out. Show empty space where stock was. Creates FOMO for the NEXT drop. People who missed out set alarms. People who copped feel validated.",
        "psychology": "Proof of demand is the strongest social proof. Seeing something sold out triggers 'I need to be faster next time.' Also validates your scarcity claim — you said limited and meant it.",
        "proof": [
            ("Corteiz", "'Sold Out' badges stay visible permanently. Past items serve as proof that demand is real."),
            ("Trapstar", "Archive Drop category shows sold-out items. Builds urgency for future releases."),
        ],
        "shots": [
            "Empty table where stock was — maybe remnants (tissue paper, a tag)",
            "Cut to website showing 'Sold Out'",
            "Optional: montage of packing process from when orders came in",
        ],
        "text_overlay": "Sold out. Next drop: [date].",
        "cta": "Follow so you don't miss the next one.",
    },
    {
        "id": 16,
        "title": "Build-a-Fit on the Beat",
        "hook": "Building the perfect fit piece by piece.",
        "category": "engagement",
        "tags": ["engagement", "awareness", "conversion"],
        "potential": 83,
        "difficulty": 2,
        "platforms": ["TikTok", "Reels"],
        "duration": "15-20 sec",
        "why": "Empty surface → items placed one by one on the beat. Satisfying rhythm + visual of outfit coming together = saves and shares. Shows the piece styled in context.",
        "psychology": "Aspirational content that lets viewers picture the full outfit. Beat-sync is native to TikTok. High save rate because people bookmark outfit ideas.",
        "proof": [
            ("Fashion TikTok", "Build-a-fit videos are top-performing. Beat-synchronized placement creates satisfying, shareable content."),
            ("Streetwear creators", "Flat lay outfit builds get 100K-500K views when synced to trending sounds."),
        ],
        "shots": [
            "Empty clean surface (top-down angle)",
            "Place shoes on the beat",
            "Place pants on the beat",
            "Place NEWGARMENTS hoodie on the beat (centerpiece)",
            "Place accessories on final beats",
            "Hold on completed outfit 2-3 seconds",
        ],
        "text_overlay": "The full fit. Hoodie drops [date].",
        "cta": "Link in bio.",
    },
    {
        "id": 17,
        "title": '"Why I Started This Brand"',
        "hook": "I was tired of paying premium for garbage. So I made my own.",
        "category": "brand",
        "tags": ["brand", "trust"],
        "potential": 85,
        "difficulty": 2,
        "platforms": ["TikTok"],
        "duration": "30-60 sec",
        "why": "Founder stories are the #1 trust builder. Gen Z wants the person behind the brand. When they know your 'why,' they root for you. Customers become supporters.",
        "psychology": "Every successful small brand has a visible founder. Gen Z trusts people, not logos. Sharing your frustration makes you relatable — 'one of them' instead of 'another brand.'",
        "proof": [
            ("Represent Clo", "George and Michael Heaton appear regularly. Founder visibility was key to scaling from bedroom to multi-million business."),
            ("Broken Planet", "Founder-led 'why we exist' content drove initial viral growth."),
            ("Corteiz", "Clint419's personality IS the brand. His visibility is inseparable from success."),
        ],
        "shots": [
            "Talk directly to camera — raw, not scripted",
            "Share the frustration that led to starting NEWGARMENTS",
            "Show products as you talk about what you built differently",
            "Be honest about the journey — imperfection is authentic",
            "End with your mission",
        ],
        "text_overlay": "Not another brand. A standard.",
        "cta": "This is why we exist. Link in bio.",
    },
    {
        "id": 18,
        "title": "The Tag / Label Shot",
        "hook": "Not Gildan. Not a blank. Built from scratch.",
        "category": "trust",
        "tags": ["trust"],
        "potential": 75,
        "difficulty": 1,
        "platforms": ["TikTok", "Reels"],
        "duration": "5-8 sec",
        "why": "Simple close-up of your label. Quick, kills the biggest suspicion. A brand's own label (not generic blank) signals the product is original.",
        "psychology": "The first thing a quality buyer checks is the label. Showing it proactively removes doubt before purchase.",
        "proof": [
            ("r/streetwearstartup", "Custom labels are consistently cited as the difference between 'legitimate brand' and 'guy printing on Gildan.'"),
        ],
        "shots": [
            "Close-up of brand tag/label",
            "Slowly pull it into focus",
            "Show woven details, custom text, or design elements",
        ],
        "text_overlay": "Not Gildan. Not a blank. Built from scratch.",
        "cta": "Link in bio.",
    },
    {
        "id": 19,
        "title": "\"Would You Cop?\" Poll",
        "hook": "Would you cop? Yes or nah.",
        "category": "engagement",
        "tags": ["engagement", "awareness"],
        "potential": 76,
        "difficulty": 1,
        "platforms": ["TikTok", "Stories"],
        "duration": "8-10 sec",
        "why": "Simplest engagement format. Show the piece, ask yes or no. Comments flood in. Drives engagement + gives real market feedback on demand.",
        "psychology": "Binary choice = zero friction to engage. Even 'nah' is engagement. 'Yes' comments create social proof.",
        "proof": [
            ("Universal format", "'Would you cop?' is the native streetwear language version of a purchase intent survey. Works across every platform."),
        ],
        "shots": [
            "Show the piece — flat lay, held up, or on body",
            "That's it. Keep it simple.",
        ],
        "text_overlay": "Would you cop? Yes or nah",
        "cta": "Drop date in comments.",
    },
    {
        "id": 20,
        "title": "Detail You Missed (Series)",
        "hook": "Details most brands skip.",
        "category": "brand",
        "tags": ["brand", "trust", "awareness"],
        "potential": 81,
        "difficulty": 1,
        "platforms": ["TikTok", "Reels"],
        "duration": "8-12 sec",
        "why": "Repeatable series — each video zooms into ONE detail. Shows obsessive attention that separates you from brands cutting corners. Micro-details signal macro-quality.",
        "psychology": "If you care about the drawstring cord, you probably care about everything else. Educates the audience to notice details — once they notice, every future hoodie gets compared.",
        "proof": [
            ("Cole Buxton", "Built brand around obsessive detail content. Each video reinforces premium positioning."),
            ("Aimé Leon Dore", "Known for small details that become talking points and cultural capital."),
        ],
        "shots": [
            "Extreme close-up on one specific detail",
            "Fingers pointing to or interacting with the detail",
            "Pull back slightly to show detail in context",
        ],
        "text_overlay": "Details most brands skip. Ep. [number]",
        "cta": "Follow for more.",
    },
    {
        "id": 21,
        "title": "Countdown Drop Teaser Series",
        "hook": "3 days.",
        "category": "fomo",
        "tags": ["fomo", "brand", "awareness"],
        "potential": 86,
        "difficulty": 1,
        "platforms": ["TikTok", "Reels", "Stories"],
        "duration": "5-10 sec each",
        "why": "A 3-day series builds narrative arc. Each post reveals more. Day 3: texture. Day 2: silhouette. Day 1: full reveal. Creates anticipation without being cringe because each reveal is calm.",
        "psychology": "The slow reveal creates investment. By day 3, they've mentally committed to checking the drop. This is how Corteiz and Trapstar build hype — through anticipation, not desperation.",
        "proof": [
            ("Corteiz", "Cryptic teasers generate massive speculation. The less you show, the more people talk."),
            ("Trapstar", "Phased reveal strategy across Stories and posts. Each layer drives engagement."),
        ],
        "shots": [
            "Day 3: Extreme close-up of texture/color. Just a date.",
            "Day 2: Silhouette of the piece. Maybe a detail.",
            "Day 1: Full product reveal with specs.",
            "Drop day: 'Live now. Link in bio.'",
        ],
        "text_overlay": "3 days. / 2 days. / Tomorrow. / Live now.",
        "cta": "Follow to not miss it.",
    },
    {
        "id": 22,
        "title": 'Comment Reply: "Is This Worth It?"',
        "hook": "Someone asked if this is worth it. Here's my answer.",
        "category": "conversion",
        "tags": ["conversion", "trust", "engagement"],
        "potential": 87,
        "difficulty": 2,
        "platforms": ["TikTok"],
        "duration": "20-30 sec",
        "why": "Reply-to-comment is native TikTok — feels like conversation, not marketing. Addresses objections publicly. Every viewer with the same question gets answered.",
        "psychology": "When someone asks 'is this worth it?' every potential customer has that question. Answering with visual proof answers it for thousands at once.",
        "proof": [
            ("TikTok native", "Reply-to-comment videos outperform standard posts. Algorithm favors content that continues conversations."),
            ("Small brand strategy", "Replying to skeptical comments with video proof converts doubters to customers."),
        ],
        "shots": [
            "Show the comment on screen",
            "Pick up hoodie — show weight, fabric, construction",
            "Flip inside out, show stitching",
            "Quick fit check",
            "End: 'You tell me if it's worth it.'",
        ],
        "text_overlay": "Replying to @[user]",
        "cta": "Link in bio. Judge for yourself.",
    },
    {
        "id": 23,
        "title": "One Piece, Three Ways",
        "hook": "1 hoodie. 3 fits. 0 misses.",
        "category": "engagement",
        "tags": ["engagement", "conversion", "awareness"],
        "potential": 82,
        "difficulty": 2,
        "platforms": ["TikTok", "IG Carousel"],
        "duration": "15-20 sec",
        "why": "Shows versatility — one piece styled three ways. Proves value by showing it works with multiple outfits. Carousels get 2-3x more saves on IG.",
        "psychology": "When one piece works in three contexts, the viewer does mental math: 'that's not one outfit, that's three.' Increases perceived value.",
        "proof": [
            ("Fashion TikTok/Instagram", "Outfit versatility content is a top-saved format. People bookmark for styling inspiration."),
        ],
        "shots": [
            "Fit 1: Hoodie + cargos + chunky sneakers",
            "Fit 2: Hoodie + wide jeans + New Balance",
            "Fit 3: Hoodie + joggers + AF1s",
            "For carousel: one slide per fit + detail slide + price",
        ],
        "text_overlay": "1 hoodie. 3 fits.",
        "cta": "Which fit is yours? Comment below.",
    },
    {
        "id": 24,
        "title": "The Slow Reveal",
        "hook": "Something's dropping soon.",
        "category": "fomo",
        "tags": ["fomo", "awareness"],
        "potential": 79,
        "difficulty": 1,
        "platforms": ["TikTok", "Reels"],
        "duration": "8-12 sec",
        "why": "Dark cloth over product → slowly pull away → reveal timed to beat drop. Simple, cinematic, builds anticipation. The reveal creates a dopamine hit.",
        "psychology": "The brain craves completion. Something partially hidden = NEED to see the rest. Drives follows and saves.",
        "proof": [
            ("Product reveal TikToks", "Beat-synced reveals consistently perform well. Combines satisfying visuals with anticipation."),
        ],
        "shots": [
            "Clean surface with dark cloth over product",
            "Slowly pull cloth away — time reveal to a beat drop",
            "Hold on revealed product 2-3 seconds",
        ],
        "text_overlay": "Dropping [date]. No restock.",
        "cta": "Follow to not miss it.",
    },
    {
        "id": 25,
        "title": "The Hanger Test",
        "hook": "Left: fast fashion. Right: NEWGARMENTS.",
        "category": "awareness",
        "tags": ["awareness", "trust"],
        "potential": 77,
        "difficulty": 1,
        "platforms": ["TikTok", "Reels"],
        "duration": "10-15 sec",
        "why": "Hang yours next to a thin one. The drape difference is immediately visible. Heavyweight holds shape, thin droops limp. Zero explanation needed.",
        "psychology": "Side-by-side on a neutral object (hanger) feels objective. They'll notice this every time they look at their own closet.",
        "proof": [
            ("Fashion quality content", "A/B comparisons make invisible qualities visible and obvious. Highly shareable format."),
        ],
        "shots": [
            "Two identical hangers side by side",
            "Thin hoodie on left — droopy, limp",
            "NEWGARMENTS on right — structured, weighted drape",
            "Camera slowly pans between the two",
        ],
        "text_overlay": "Left: fast fashion. Right: NEWGARMENTS.",
        "cta": "Link in bio.",
    },
    {
        "id": 26,
        "title": "Spec Slide Carousel",
        "hook": "Everything you need to know in 6 slides.",
        "category": "conversion",
        "tags": ["conversion", "trust"],
        "potential": 84,
        "difficulty": 1,
        "platforms": ["IG Carousel"],
        "duration": "6-8 slides",
        "why": "Each slide = one close-up + one spec. Carousels get highest save rate on IG (2-3x single images). This is your product page in social format.",
        "psychology": "Spec-by-spec reveals build a case like evidence. By the price slide, they're already convinced of value.",
        "proof": [
            ("Instagram algorithm", "Carousels outperform single images in saves. Swipe increases dwell time = algorithmic boost."),
            ("DTC brands", "Product carousel breakdowns are the highest-converting organic IG format for fashion."),
        ],
        "shots": [
            "Slide 1: Full piece flat lay — product name",
            "Slide 2: Fabric close-up — '460 GSM French Terry'",
            "Slide 3: Stitching — 'Double Stitched Seams'",
            "Slide 4: Cuff — 'Reinforced Ribbing'",
            "Slide 5: Label — 'Designed in the Netherlands'",
            "Slide 6: Styled — price + 'No restock.'",
        ],
        "text_overlay": "One spec per slide.",
        "cta": "Link in bio. Limited pieces.",
    },
    {
        "id": 27,
        "title": "\"This or That\" Colorway Poll",
        "hook": "Which colorway would you cop?",
        "category": "engagement",
        "tags": ["engagement", "awareness"],
        "potential": 77,
        "difficulty": 1,
        "platforms": ["TikTok", "Stories"],
        "duration": "8-10 sec",
        "why": "Two colorways side by side. Ask which they'd cop. Comments flood in. Engagement gold + real market data on demand.",
        "psychology": "Binary choices are irresistible. The debate creates organic reach. Asking their opinion makes them feel like collaborators, not customers.",
        "proof": [
            ("Universal format", "'This or That' works across every niche. Colorway debates drive some of the highest comment counts in streetwear."),
        ],
        "shots": [
            "Two pieces side by side — different colorways",
            "Or: split screen with one on each side",
        ],
        "text_overlay": "Left or right?",
        "cta": "Winning colorway drops first.",
    },
    {
        "id": 28,
        "title": "Archive Piece (Past Drop)",
        "hook": "This is archive now. 0 left. 0 restocks.",
        "category": "fomo",
        "tags": ["fomo", "brand"],
        "potential": 83,
        "difficulty": 1,
        "platforms": ["TikTok", "Reels"],
        "duration": "12-18 sec",
        "why": "Show a previous sold-out piece. Proves no-restock is real. Creates FOMO for current/next drop. If past items are truly gone, they won't hesitate next time.",
        "psychology": "Loss aversion is one of the strongest drivers. Something permanently unavailable triggers regret → action on next drop.",
        "proof": [
            ("Corteiz", "'Sold Out' badges remain permanently. The single most effective FOMO mechanism."),
            ("Trapstar", "'Archive Drop' category turns past products into marketing tools."),
        ],
        "shots": [
            "Hold up or show the sold-out piece",
            "Detail shots — fabric, stitching, design",
            "Show website listing as 'Sold Out'",
        ],
        "text_overlay": "Archive. Never coming back. The next drop won't last either.",
        "cta": "Next drop: [date]. Don't sleep.",
    },
    {
        "id": 29,
        "title": "Mirror Fit Check",
        "hook": "New piece. 460 GSM. Boxy fit. Thoughts?",
        "category": "awareness",
        "tags": ["awareness", "engagement"],
        "potential": 79,
        "difficulty": 1,
        "platforms": ["TikTok", "Reels"],
        "duration": "10-15 sec",
        "why": "The most native streetwear format. You wearing it, phone in hand. If the founder wears the brand, it adds instant credibility. Asking 'thoughts?' invites engagement.",
        "psychology": "Fit checks are how Gen Z validates purchases. By posting one yourself, you show confidence in your product and give real-body reference.",
        "proof": [
            ("TikTok streetwear", "Fit checks are the backbone of streetwear TikTok. Billions of views on #fitcheck. Never feels like marketing."),
        ],
        "shots": [
            "Standing in front of mirror wearing the piece",
            "Show front, turn to show side, show back",
            "Specs as text overlay",
        ],
        "text_overlay": "[Piece name] / 460 GSM / Boxy fit / €[price]",
        "cta": "Link in bio.",
    },
    {
        "id": 30,
        "title": '"Stop Buying Streetwear Until You Watch This"',
        "hook": "Stop buying streetwear until you watch this.",
        "category": "awareness",
        "tags": ["awareness", "trust", "conversion"],
        "potential": 90,
        "difficulty": 2,
        "platforms": ["TikTok"],
        "duration": "30-45 sec",
        "why": "The strongest pattern-interrupt hook. Demands attention, creates curiosity gap. Then you deliver value: teach quality checks. Position your product as the example of what to look for.",
        "psychology": "Commanding hooks trigger a primal response — people stop to see if the authority is legit. When you deliver real value, authority is confirmed. Creates 'brand that educates me' dynamic.",
        "proof": [
            ("'Stop buying X' format", "One of the highest-performing hook structures on TikTok. In fashion, consistently drives 500K+ views."),
            ("Cole Buxton", "Education-first strategy turned them from unknown to most discussed premium streetwear brand."),
        ],
        "shots": [
            "Talk to camera or voiceover with product in hand",
            "Show 3 quick quality checks: weight, inside, stitching",
            "Use your hoodie as the positive example",
            "End: 'Now you know what to look for.'",
        ],
        "text_overlay": "Save this. Check before you buy anything.",
        "cta": "We pass every test. Link in bio.",
    },
]


class ContentDashboard(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("NEWGARMENTS — Content Ideas Dashboard")
        self.geometry("1280x800")
        self.minsize(900, 600)
        self.configure(bg=BG)
        self.active_filter = "all"
        self.search_var = tk.StringVar()
        self.sort_var = tk.StringVar(value="potential")
        self.active_card_id = None
        self._card_frames = []

        # Fonts
        self.font_title = tkfont.Font(family="Segoe UI", size=11, weight="bold")
        self.font_body = tkfont.Font(family="Segoe UI", size=10)
        self.font_small = tkfont.Font(family="Segoe UI", size=9)
        self.font_tiny = tkfont.Font(family="Segoe UI", size=8)
        self.font_heading = tkfont.Font(family="Segoe UI", size=14, weight="bold")
        self.font_section = tkfont.Font(family="Segoe UI", size=9, weight="bold")
        self.font_hook = tkfont.Font(family="Segoe UI", size=12, weight="bold")
        self.font_logo = tkfont.Font(family="Segoe UI", size=11, weight="bold")

        self._build_ui()
        self._render_cards()

    def _build_ui(self):
        # Header
        header = tk.Frame(self, bg=BG)
        header.pack(fill="x", padx=24, pady=(16, 8))

        tk.Label(header, text="NEWGARMENTS", font=self.font_logo, bg=BG, fg=TEXT).pack(side="left")
        tk.Label(header, text="  /  Content Dashboard", font=self.font_body, bg=BG, fg=TEXT_MUTED).pack(side="left")

        self.count_label = tk.Label(header, text="", font=self.font_small, bg=BG, fg=TEXT_SEC)
        self.count_label.pack(side="right")

        # Filters
        filter_frame = tk.Frame(self, bg=BG)
        filter_frame.pack(fill="x", padx=24, pady=(4, 4))

        filters = [("All", "all")] + [(LABELS[k], k) for k in COLORS]
        self._filter_buttons = {}
        for label, key in filters:
            btn = tk.Button(
                filter_frame, text=f"  {label}  ", font=self.font_small,
                bg=TEXT if key == "all" else SURFACE, fg=BG if key == "all" else TEXT_SEC,
                bd=0, relief="flat", cursor="hand2", padx=10, pady=4,
                activebackground=TEXT, activeforeground=BG,
                command=lambda k=key: self._set_filter(k),
            )
            btn.pack(side="left", padx=2)
            self._filter_buttons[key] = btn

        # Search and sort row
        ctrl_frame = tk.Frame(self, bg=BG)
        ctrl_frame.pack(fill="x", padx=24, pady=(4, 8))

        tk.Label(ctrl_frame, text="Search:", font=self.font_small, bg=BG, fg=TEXT_SEC).pack(side="left")
        search_entry = tk.Entry(
            ctrl_frame, textvariable=self.search_var, font=self.font_body,
            bg=SURFACE, fg=TEXT, insertbackground=TEXT, bd=0, relief="flat", width=28,
        )
        search_entry.pack(side="left", padx=(6, 16), ipady=4)
        self.search_var.trace_add("write", lambda *_: self._render_cards())

        tk.Label(ctrl_frame, text="Sort:", font=self.font_small, bg=BG, fg=TEXT_SEC).pack(side="left")
        for text, val in [("Highest Potential", "potential"), ("Easiest First", "easiest")]:
            rb = tk.Radiobutton(
                ctrl_frame, text=text, variable=self.sort_var, value=val,
                font=self.font_small, bg=BG, fg=TEXT_SEC, selectcolor=SURFACE,
                activebackground=BG, activeforeground=TEXT, indicatoron=False,
                bd=0, padx=10, pady=3, cursor="hand2",
                command=self._render_cards,
            )
            rb.pack(side="left", padx=2)

        # Separator
        tk.Frame(self, bg=BORDER, height=1).pack(fill="x")

        # Main paned area
        self.paned = tk.PanedWindow(self, orient="horizontal", bg=BG, bd=0, sashwidth=2, sashrelief="flat")
        self.paned.pack(fill="both", expand=True)

        # Left: card list
        left = tk.Frame(self.paned, bg=BG)
        self.paned.add(left, width=720, minsize=400)

        self.card_canvas = tk.Canvas(left, bg=BG, highlightthickness=0)
        self.card_scrollbar = ttk.Scrollbar(left, orient="vertical", command=self.card_canvas.yview)
        self.card_scroll_frame = tk.Frame(self.card_canvas, bg=BG)

        self.card_scroll_frame.bind("<Configure>", lambda e: self.card_canvas.configure(scrollregion=self.card_canvas.bbox("all")))
        self.card_canvas.create_window((0, 0), window=self.card_scroll_frame, anchor="nw")
        self.card_canvas.configure(yscrollcommand=self.card_scrollbar.set)

        self.card_scrollbar.pack(side="right", fill="y")
        self.card_canvas.pack(side="left", fill="both", expand=True)

        # Mouse wheel scrolling
        self.card_canvas.bind("<Enter>", lambda e: self._bind_mousewheel(self.card_canvas))
        self.card_canvas.bind("<Leave>", lambda e: self._unbind_mousewheel())

        # Right: detail panel
        right = tk.Frame(self.paned, bg=SURFACE)
        self.paned.add(right, width=520, minsize=350)

        self.detail_canvas = tk.Canvas(right, bg=SURFACE, highlightthickness=0)
        self.detail_scrollbar = ttk.Scrollbar(right, orient="vertical", command=self.detail_canvas.yview)
        self.detail_scroll_frame = tk.Frame(self.detail_canvas, bg=SURFACE)

        self.detail_scroll_frame.bind("<Configure>", lambda e: self.detail_canvas.configure(scrollregion=self.detail_canvas.bbox("all")))
        self.detail_canvas.create_window((0, 0), window=self.detail_scroll_frame, anchor="nw")
        self.detail_canvas.configure(yscrollcommand=self.detail_scrollbar.set)

        self.detail_scrollbar.pack(side="right", fill="y")
        self.detail_canvas.pack(side="left", fill="both", expand=True)

        self.detail_canvas.bind("<Enter>", lambda e: self._bind_mousewheel(self.detail_canvas))
        self.detail_canvas.bind("<Leave>", lambda e: self._unbind_mousewheel())

        self._show_empty_detail()

    def _bind_mousewheel(self, canvas):
        self._active_canvas = canvas
        self.bind_all("<MouseWheel>", self._on_mousewheel)

    def _unbind_mousewheel(self):
        self.unbind_all("<MouseWheel>")

    def _on_mousewheel(self, event):
        if hasattr(self, '_active_canvas'):
            self._active_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def _set_filter(self, key):
        self.active_filter = key
        for k, btn in self._filter_buttons.items():
            if k == key:
                btn.configure(bg=TEXT, fg=BG)
            else:
                btn.configure(bg=SURFACE, fg=TEXT_SEC)
        self._render_cards()

    def _get_filtered(self):
        query = self.search_var.get().lower()
        filtered = []
        for idea in IDEAS:
            if self.active_filter != "all" and self.active_filter not in idea["tags"]:
                continue
            if query and query not in idea["title"].lower() and query not in idea["hook"].lower() and query not in idea["why"].lower():
                continue
            filtered.append(idea)

        sort = self.sort_var.get()
        if sort == "potential":
            filtered.sort(key=lambda x: -x["potential"])
        elif sort == "easiest":
            filtered.sort(key=lambda x: (x["difficulty"], -x["potential"]))
        return filtered

    def _render_cards(self):
        for w in self.card_scroll_frame.winfo_children():
            w.destroy()
        self._card_frames = []
        filtered = self._get_filtered()

        self.count_label.configure(text=f"{len(filtered)} of {len(IDEAS)} ideas")

        for idea in filtered:
            self._create_card(idea)

    def _create_card(self, idea):
        is_active = self.active_card_id == idea["id"]
        card_bg = SURFACE_ACTIVE if is_active else SURFACE

        card = tk.Frame(self.card_scroll_frame, bg=card_bg, highlightbackground=BORDER if not is_active else "#444", highlightthickness=1, cursor="hand2")
        card.pack(fill="x", padx=12, pady=4)
        card.bind("<Button-1>", lambda e, i=idea: self._open_detail(i))

        # Make all children also trigger click
        def bind_children(widget, idea):
            widget.bind("<Button-1>", lambda e, i=idea: self._open_detail(i))
            for child in widget.winfo_children():
                bind_children(child, idea)

        # Top row: number + tags
        top = tk.Frame(card, bg=card_bg)
        top.pack(fill="x", padx=14, pady=(10, 2))

        tk.Label(top, text=f"#{idea['id']:02d}", font=self.font_tiny, bg=card_bg, fg=TEXT_MUTED).pack(side="left")

        tag_frame = tk.Frame(top, bg=card_bg)
        tag_frame.pack(side="right")
        for t in idea["tags"]:
            color = COLORS.get(t, TEXT)
            tk.Label(tag_frame, text=f" {LABELS[t]} ", font=self.font_tiny, bg=card_bg, fg=color).pack(side="left", padx=1)

        # Title
        tk.Label(card, text=idea["title"], font=self.font_title, bg=card_bg, fg=TEXT, anchor="w").pack(fill="x", padx=14, pady=(0, 2))

        # Hook
        tk.Label(card, text=f'"{idea["hook"]}"', font=self.font_small, bg=card_bg, fg=TEXT_SEC, anchor="w", wraplength=600, justify="left").pack(fill="x", padx=14, pady=(0, 4))

        # Meta row
        meta = tk.Frame(card, bg=card_bg)
        meta.pack(fill="x", padx=14, pady=(2, 4))

        platforms = " / ".join(idea["platforms"])
        tk.Label(meta, text=platforms, font=self.font_tiny, bg=card_bg, fg=TEXT_MUTED).pack(side="left", padx=(0, 12))
        tk.Label(meta, text=idea["duration"], font=self.font_tiny, bg=card_bg, fg=TEXT_MUTED).pack(side="left", padx=(0, 12))
        tk.Label(meta, text=f"Difficulty: {idea['difficulty']}/3", font=self.font_tiny, bg=card_bg, fg=TEXT_MUTED).pack(side="left", padx=(0, 12))

        # Potential bar
        bar_frame = tk.Frame(card, bg=card_bg)
        bar_frame.pack(fill="x", padx=14, pady=(0, 10))

        bar_bg_canvas = tk.Canvas(bar_frame, height=4, bg=BORDER, highlightthickness=0)
        bar_bg_canvas.pack(fill="x")

        color = COLORS.get(idea["category"], TEXT)
        potential = idea["potential"]
        bar_bg_canvas.update_idletasks()
        bar_bg_canvas.bind("<Configure>", lambda e, c=bar_bg_canvas, p=potential, col=color: self._draw_bar(c, p, col))

        bind_children(card, idea)
        self._card_frames.append(card)

    def _draw_bar(self, canvas, potential, color):
        canvas.delete("bar")
        w = canvas.winfo_width()
        fill_w = int(w * potential / 100)
        canvas.create_rectangle(0, 0, fill_w, 4, fill=color, outline="", tags="bar")

    def _show_empty_detail(self):
        for w in self.detail_scroll_frame.winfo_children():
            w.destroy()
        tk.Label(self.detail_scroll_frame, text="Click an idea to see details", font=self.font_body, bg=SURFACE, fg=TEXT_MUTED).pack(pady=100)

    def _open_detail(self, idea):
        self.active_card_id = idea["id"]
        self._render_cards()

        for w in self.detail_scroll_frame.winfo_children():
            w.destroy()

        f = self.detail_scroll_frame
        pad_x = 24

        # Title
        tk.Label(f, text=f"IDEA #{idea['id']:02d}", font=self.font_tiny, bg=SURFACE, fg=TEXT_MUTED, anchor="w").pack(fill="x", padx=pad_x, pady=(20, 2))
        tk.Label(f, text=idea["title"], font=self.font_heading, bg=SURFACE, fg=TEXT, anchor="w", wraplength=440, justify="left").pack(fill="x", padx=pad_x, pady=(0, 8))

        # Tags
        tag_row = tk.Frame(f, bg=SURFACE)
        tag_row.pack(fill="x", padx=pad_x, pady=(0, 6))
        for t in idea["tags"]:
            color = COLORS.get(t, TEXT)
            lbl = tk.Label(tag_row, text=f" {LABELS[t]} ", font=self.font_tiny, bg=SURFACE, fg=color)
            lbl.pack(side="left", padx=(0, 6))

        # Platforms
        plat_row = tk.Frame(f, bg=SURFACE)
        plat_row.pack(fill="x", padx=pad_x, pady=(0, 12))
        for p in idea["platforms"]:
            tk.Label(plat_row, text=f" {p} ", font=self.font_tiny, bg=BG, fg=TEXT_SEC, padx=6, pady=2).pack(side="left", padx=(0, 4))

        # Metrics
        metrics_frame = tk.Frame(f, bg=SURFACE)
        metrics_frame.pack(fill="x", padx=pad_x, pady=(0, 12))

        color = COLORS.get(idea["category"], TEXT)
        self._metric_box(metrics_frame, "POTENTIAL", f"{idea['potential']}/100", color, 0)
        self._metric_box(metrics_frame, "DIFFICULTY", "●" * idea["difficulty"] + "○" * (3 - idea["difficulty"]), TEXT, 1)
        self._metric_box(metrics_frame, "DURATION", idea["duration"], TEXT_SEC, 2)
        self._metric_box(metrics_frame, "PRIMARY", LABELS[idea["category"]], color, 3)

        for i in range(4):
            metrics_frame.grid_columnconfigure(i, weight=1)

        # Hook box
        hook_frame = tk.Frame(f, bg=BG, highlightbackground=BORDER, highlightthickness=1)
        hook_frame.pack(fill="x", padx=pad_x, pady=(0, 16))
        tk.Label(hook_frame, text="HOOK (FIRST 3 SECONDS)", font=self.font_tiny, bg=BG, fg=TEXT_MUTED, anchor="w").pack(fill="x", padx=14, pady=(10, 2))
        tk.Label(hook_frame, text=f'"{idea["hook"]}"', font=self.font_hook, bg=BG, fg=TEXT, anchor="w", wraplength=420, justify="left").pack(fill="x", padx=14, pady=(0, 12))

        # Sections
        self._detail_section(f, "WHY THIS WORKS", idea["why"], pad_x)
        self._detail_section(f, "PSYCHOLOGY BEHIND IT", idea["psychology"], pad_x)

        # Proof
        self._section_header(f, "WHERE THIS HAS WORKED BEFORE", pad_x)
        for brand, detail in idea["proof"]:
            proof_frame = tk.Frame(f, bg=BG, highlightbackground=BORDER, highlightthickness=1)
            proof_frame.pack(fill="x", padx=pad_x, pady=(0, 6))
            tk.Label(proof_frame, text=brand, font=self.font_section, bg=BG, fg=TEXT, anchor="w").pack(fill="x", padx=12, pady=(8, 0))
            tk.Label(proof_frame, text=detail, font=self.font_small, bg=BG, fg=TEXT_MUTED, anchor="w", wraplength=420, justify="left").pack(fill="x", padx=12, pady=(2, 8))
        tk.Frame(f, bg=SURFACE, height=12).pack(fill="x")

        # Shot list
        self._section_header(f, "SHOT LIST (WHAT TO FILM)", pad_x)
        for i, shot in enumerate(idea["shots"], 1):
            row = tk.Frame(f, bg=SURFACE)
            row.pack(fill="x", padx=pad_x, pady=1)
            tk.Label(row, text=f"{i}.", font=self.font_tiny, bg=SURFACE, fg=TEXT_MUTED, width=3, anchor="ne").pack(side="left", anchor="n", pady=2)
            tk.Label(row, text=shot, font=self.font_small, bg=SURFACE, fg=TEXT_SEC, anchor="w", wraplength=400, justify="left").pack(side="left", fill="x", expand=True, pady=2)
        tk.Frame(f, bg=SURFACE, height=16).pack(fill="x")

        # Text overlay
        self._section_header(f, "TEXT OVERLAY", pad_x)
        tk.Label(f, text=idea["text_overlay"], font=self.font_body, bg=SURFACE, fg=TEXT, anchor="w", wraplength=440, justify="left").pack(fill="x", padx=pad_x, pady=(0, 16))

        # CTA
        self._section_header(f, "CALL TO ACTION", pad_x)
        tk.Label(f, text=idea["cta"], font=self.font_body, bg=SURFACE, fg=TEXT, anchor="w", wraplength=440, justify="left").pack(fill="x", padx=pad_x, pady=(0, 24))

        # Scroll to top
        self.detail_canvas.yview_moveto(0)

    def _metric_box(self, parent, label, value, color, col):
        box = tk.Frame(parent, bg=BG, highlightbackground=BORDER, highlightthickness=1)
        box.grid(row=0, column=col, padx=2, sticky="nsew")
        tk.Label(box, text=label, font=self.font_tiny, bg=BG, fg=TEXT_MUTED).pack(padx=8, pady=(8, 0))
        tk.Label(box, text=value, font=self.font_title, bg=BG, fg=color).pack(padx=8, pady=(0, 8))

    def _section_header(self, parent, text, pad_x):
        tk.Label(parent, text=text, font=self.font_section, bg=SURFACE, fg=TEXT_SEC, anchor="w").pack(fill="x", padx=pad_x, pady=(0, 6))

    def _detail_section(self, parent, title, text, pad_x):
        self._section_header(parent, title, pad_x)
        tk.Label(parent, text=text, font=self.font_small, bg=SURFACE, fg=TEXT_SEC, anchor="w", wraplength=440, justify="left").pack(fill="x", padx=pad_x, pady=(0, 16))


if __name__ == "__main__":
    # Style the scrollbars
    app = ContentDashboard()
    style = ttk.Style()
    style.theme_use("default")
    style.configure("Vertical.TScrollbar", background=SURFACE, troughcolor=BG, bordercolor=BG, arrowcolor=TEXT_MUTED)
    app.mainloop()
