#!/usr/bin/env python3
"""Build the Safwa presentation website without third-party dependencies."""
from pathlib import Path
from html import escape

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / 'dist'

MISSION = 'To create a space for Muslim women to deepen their faith, pursue meaningful knowledge, and grow into more intentional versions of themselves.'
VISION = 'To nurture a generation of Muslim women whose faith grounds them, whose knowledge guides them, and whose growth reflects in how they live, choose, and contribute to the world.'
INSTAGRAM = 'https://www.instagram.com/safwa.institute/'
STUDIOS_INSTAGRAM = 'https://www.instagram.com/safwa.studios/'
PARENT_INSTAGRAM = 'https://www.instagram.com/thesafwa_/'
WHATSAPP_COMMUNITY = 'https://chat.whatsapp.com/EFa8nIHGs52A5tw0XbPiPQ'
WEBSITE_ORIGIN = 'https://thesafwa.onrender.com'

def brand_crop(asset, box, label, css=''):
    return f'<svg class="{css}" viewBox="{box}" role="img" aria-label="{escape(label)}" xmlns="http://www.w3.org/2000/svg"><image href="/assets/{asset}" width="{1254 if asset == "the-safwa-logo.jpg" else 1152}" height="{1254 if asset == "the-safwa-logo.jpg" else 2048}"/></svg>'

def studio_brand():
    return f'<div class="studio-brand-visual">{brand_crop("studios-brand.jpg", "197 512 760 760", "Safwa Studios — Media, Refined")}</div>'

def atmosphere(label=False):
    # Render a text-free window into the supplied image; original bytes are unchanged.
    return '<figure class="atmosphere"><svg viewBox="260 1120 790 520" preserveAspectRatio="xMidYMid slice" role="img" aria-label="Warm sunlight, a cup and delicate flowers beside an open window" xmlns="http://www.w3.org/2000/svg"><image href="/assets/institute-atmosphere.jpg" width="1152" height="2048"/></svg>' + ('<figcaption class="photo-label">Room to reflect. Space to grow.</figcaption>' if label else '') + '</figure>'

def star():
    return '<svg viewBox="0 0 40 40" aria-hidden="true"><path d="M20 2c0 12-6 18-18 18 12 0 18 6 18 18 0-12 6-18 18-18C26 20 20 14 20 2Z" fill="none" stroke="currentColor" stroke-width="1"/></svg>'

def book():
    return f'<div class="book-scene" role="img" aria-label="Decorative book bearing the project name Safwa Quran"><div class="big-book">{star()}<span class="book-title">Safwa</span><span class="book-subtitle">QURAN</span></div><span class="book-note">Safwa Quran · A project in development</span></div>'

def link(text, href, cls='arrow-link', external=False):
    extra = ' target="_blank" rel="noopener noreferrer"' if external else ''
    accessible = '<span class="visually-hidden"> (opens in a new tab)</span>' if external else ''
    return f'<a class="{cls}" href="{escape(href)}"{extra}><span>{text}{accessible}</span><span class="arrow" aria-hidden="true">↗</span></a>'

def header(current):
    nav = [('home','Our world','/#world'),('institute','Institute','/institute.html'),('studios','Studios','/studios.html'),('quran','Safwa Quran','/quran.html')]
    items = ''.join(f'<a href="{href}"' + (' aria-current="page"' if key == current else '') + f'>{name}</a>' for key,name,href in nav)
    mobile = ''.join(f'<a href="{href}">{name}<span aria-hidden="true">0{i+1} ↗</span></a>' for i,(_,name,href) in enumerate(nav))
    return f'''<a class="skip-link" href="#main">Skip to content</a>
<header class="site-header">
 <a class="brand" href="/" aria-label="The Safwa, home">{brand_crop('the-safwa-logo.jpg','565 305 150 420','The Safwa gold pillar','logo-pillar')}{brand_crop('the-safwa-logo.jpg','165 760 930 245','The Safwa — Excellence, Refined','logo-wordmark')}</a>
 <nav class="desktop-nav" aria-label="Main navigation">{items}</nav>
 <div class="header-actions"><a class="header-contact" href="/connect.html">Connect with us <span aria-hidden="true">↗</span></a><button class="menu-toggle" aria-controls="mobile-navigation" aria-expanded="false" aria-label="Open navigation menu">Menu<i aria-hidden="true"></i></button></div>
</header>
<nav id="mobile-navigation" class="mobile-nav" aria-label="Mobile navigation">{mobile}<a href="/connect.html">Connect<span aria-hidden="true">05 ↗</span></a><p class="eyebrow">The Safwa · Excellence, Refined.</p></nav>'''

def footer():
    return f'''<footer class="site-footer wrap"><div class="footer-top"><a href="/" aria-label="The Safwa, home"><div class="footer-brand">THE SAFWA</div><p class="footer-tagline">Excellence, Refined.</p></a><nav class="footer-links" aria-label="Footer navigation"><a href="/institute.html">Institute</a><a href="/studios.html">Studios</a><a href="/quran.html">Safwa Quran</a><a href="/connect.html">Connect</a></nav></div><nav class="footer-socials" aria-label="Safwa social and community links">{link("The Safwa",PARENT_INSTAGRAM,cls="social-link",external=True)}{link("Safwa Institute",INSTAGRAM,cls="social-link",external=True)}{link("Safwa Studios",STUDIOS_INSTAGRAM,cls="social-link",external=True)}{link("WhatsApp community",WHATSAPP_COMMUNITY,cls="social-link",external=True)}</nav><div class="footer-bottom"><span>© 2026 The Safwa. Faith, knowledge &amp; purposeful growth.</span><button type="button" data-open-privacy>Privacy &amp; enquiries</button></div></footer>
<dialog class="privacy-dialog" aria-labelledby="privacy-title"><h2 id="privacy-title">Privacy, with care.</h2><p>This website introduces The Safwa and its initiatives. It does not provide accounts, receive applications or accept document uploads.</p><p>The enquiry tool prepares a message in your browser. It does not send your message to a server or save your form entries in website storage. When you choose “Copy message”, the text is placed on your device’s clipboard.</p><p>Instagram and WhatsApp open separately. You choose whether to send a message or join the community. Those services handle information under their own policies.</p><p>This site includes no advertising trackers or visitor analytics. Hosting providers may process routine connection information needed to serve the website.</p><button type="button" class="button" data-close-privacy>Close <span aria-hidden="true">×</span></button></dialog>'''

def contact_band():
    return f'''<section class="contact-band wrap" aria-labelledby="contact-band-title"><div><p class="eyebrow">Every meaningful journey begins somewhere.</p><h2 id="contact-band-title">Let’s begin<br><em>a conversation.</em></h2></div><div class="contact-band-right"><p>A question, an idea, or a desire to learn. There is a place to begin.</p>{link('Connect with Safwa','/connect.html')}</div></section>'''

HOME = f'''
<section class="home-hero wrap" aria-labelledby="hero-title">
 <div class="hero-copy"><p class="eyebrow">Welcome to the world of The Safwa</p><h1 id="hero-title">Excellence,<br><em>with purpose.</em></h1><p>Rooted in faith. Guided by knowledge.<br>A shared vision for a more intentional life.</p>{link('Explore our world','#world')}<div class="hero-bottom"><span>FAITH. KNOWLEDGE. GROWTH.</span><span class="line"></span><span>SCROLL TO DISCOVER ↓</span></div></div>
 <figure class="hero-visual"><div class="horse-frame"><img src="/assets/white-horse.jpg" alt="A white horse in a finely detailed bridle, from the supplied Safwa brand imagery" width="1070" height="1070" fetchpriority="high"></div><span class="floating-note" aria-hidden="true">{star()}</span><figcaption class="visual-caption"><span>A quiet strength. A clear purpose.</span><span>THE SAFWA / 01</span></figcaption></figure>
</section>
<section class="intro wrap hairline" aria-labelledby="intro-title"><p class="eyebrow">One vision. Thoughtfully expressed.</p><h2 id="intro-title">Faith that grounds us.<br>Knowledge that guides us.<br><em>Growth that becomes a way of life.</em></h2><p>Welcome to a world of learning, creativity and intention. Explore the different expressions of The Safwa.</p></section>
<section id="world" class="world wrap" aria-labelledby="world-title"><div class="section-topline"><h2 id="world-title" class="eyebrow">The Safwa, at a glance</h2><span class="small-note">Discover your path ↙</span></div><div class="world-grid">
 <a class="world-card" href="/institute.html"><span class="eyebrow">01 / Learning &amp; belonging</span><p class="world-quote">A space to learn.<br><em>A life to grow into.</em></p><img class="card-art institute-mark" src="/assets/institute-logo.jpg" alt="" width="1024" height="1024" loading="lazy"><h3>Safwa Institute</h3><div class="card-bottom"><span>Faith, knowledge &amp; growth</span><span class="arrow" aria-hidden="true">↗</span></div></a>
 <a class="world-card studio-card" href="/studios.html"><span class="eyebrow">02 / Creative expression</span><div class="card-art">{brand_crop('studios-brand.jpg','197 512 760 760','Safwa Studios logo')}</div><h3>Safwa Studios</h3><div class="card-bottom"><span>Media, refined.</span><span class="arrow" aria-hidden="true">↗</span></div></a>
 <a class="world-card quran-card" href="/quran.html"><span class="eyebrow">03 / Digital reflection</span><div class="card-art" aria-hidden="true"><div class="small-book"></div></div><h3>Safwa Quran</h3><div class="card-bottom"><span class="status">In development</span><span class="arrow" aria-hidden="true">↗</span></div></a>
</div></section>
<section class="institute-feature wrap hairline" aria-labelledby="institute-feature-title">{atmosphere(True)}<div class="feature-copy"><p class="eyebrow">Safwa Institute</p><h2 id="institute-feature-title">Room for faith.<br>Space for<br><em>becoming.</em></h2><p>A space for Muslim women to deepen their faith, pursue meaningful knowledge, and grow into more intentional versions of themselves.</p>{link('Explore the Institute','/institute.html')}</div></section>
<section class="studio-feature wrap" aria-labelledby="studios-feature-title"><div class="studio-feature-grid"><div><p class="eyebrow">Safwa Studios / Media, Refined.</p><h2 id="studios-feature-title">Thoughtfully made.<br><em>Beautifully told.</em></h2><p>A refined creative identity. A considered approach to ideas, stories and digital expression.</p>{link('Discover the Studios','/studios.html')}</div>{studio_brand()}</div></section>
<section class="quran-feature wrap" aria-labelledby="quran-feature-title">{book()}<div><p class="eyebrow">Safwa Quran <span aria-hidden="true">/</span> <span class="status">In development</span></p><h2 id="quran-feature-title">A quieter space.<br><em>A deeper<br>connection.</em></h2><p>A digital project centred on the Qur’an, reflection and daily practice. Discover the intention behind Safwa Quran.</p>{link('Meet Safwa Quran','/quran.html')}</div></section>
{contact_band()}
'''

INSTITUTE = f'''
<section class="inner-hero wrap" aria-labelledby="institute-title"><div><img class="institute-emblem" src="/assets/institute-logo.jpg" alt="Safwa Institute logo" width="1024" height="1024"><p class="eyebrow gold">Safwa Institute</p><h1 id="institute-title">Faith.<br>Knowledge.<br><em>Growth.</em></h1><p>Cultivating a life of faith, knowledge, and growth. A space for Muslim women to learn with intention.</p>{link('The heart of the Institute','#purpose')}</div>{atmosphere(True)}</section>
<div class="institute-intro wrap"><h2>For the woman you are.<br><em>And the woman you are becoming.</em></h2></div>
<section id="purpose" class="purpose-section wrap" aria-labelledby="purpose-title"><div><p class="eyebrow">Our purpose, in our words.</p><h2 id="purpose-title">Rooted in faith.<br><em>Looking forward.</em></h2></div><div><div class="purpose-tabs" role="tablist" aria-label="Safwa Institute purpose"><button id="mission-tab" data-purpose-tab role="tab" aria-selected="true" aria-controls="mission-panel">Our mission</button><button id="vision-tab" data-purpose-tab role="tab" aria-selected="false" aria-controls="vision-panel">Our vision</button></div><div id="mission-panel" class="purpose-panel" role="tabpanel" aria-labelledby="mission-tab" tabindex="0">{MISSION}</div><div id="vision-panel" class="purpose-panel" role="tabpanel" aria-labelledby="vision-tab" tabindex="0">{VISION}</div><p class="purpose-source">Safwa Institute · Mission &amp; vision</p></div></section>
<section class="three-values wrap" aria-label="Faith, knowledge and growth"><div class="value"><span class="eyebrow gold">01</span><h3>Faith.</h3><p>A grounding for how we live, choose and contribute to the world.</p></div><div class="value"><span class="eyebrow gold">02</span><h3>Knowledge.</h3><p>Meaningful learning that guides our understanding and intentions.</p></div><div class="value"><span class="eyebrow gold">03</span><h3>Growth.</h3><p>A continuing journey towards more intentional versions of ourselves.</p></div></section>
<section class="opportunities wrap" aria-labelledby="opportunities-title"><div class="opportunities-heading"><h2 id="opportunities-title">Find your<br><em>next beginning.</em></h2><p>Speak with the Institute about current learning opportunities, admissions and ways to connect.</p></div>
<a class="opportunity-row" href="/connect.html?interest=learning"><span class="index">01</span><h3>Learning at Safwa</h3><p>Ask about current programmes, study areas and how to get started.</p><span class="arrow" aria-hidden="true">↗</span></a>
<a class="opportunity-row" href="/connect.html?interest=admissions"><span class="index">02</span><h3>Admissions &amp; scholarships</h3><p>Request current dates, eligibility details and application guidance.</p><span class="arrow" aria-hidden="true">↗</span></a>
<a class="opportunity-row" href="{WHATSAPP_COMMUNITY}" target="_blank" rel="noopener noreferrer"><span class="index">03</span><h3>Community &amp; connection<span class="visually-hidden"> (opens WhatsApp in a new tab)</span></h3><p>Open the Safwa community invitation on WhatsApp.</p><span class="arrow" aria-hidden="true">↗</span></a>
</section>{contact_band()}
'''

STUDIOS = f'''
<section class="inner-hero wrap" aria-labelledby="studios-title"><div><p class="eyebrow gold">Safwa Studios</p><h1 id="studios-title">Media,<br><em>refined.</em></h1><p>Ideas deserve intention. Stories deserve care.<br>A creative direction shaped by the Safwa standard.</p>{link('Discover the direction','#direction')}</div>{studio_brand()}</section>
<section id="direction" class="studio-statement wrap" aria-labelledby="direction-title"><p class="eyebrow gold">A considered expression.</p><h2 id="direction-title">Clarity in the idea.<br>Care in the detail.<br><em>Purpose in the work.</em></h2></section>
<section class="studio-project wrap" aria-labelledby="studio-project-title"><div><p class="eyebrow">A digital project to discover <span aria-hidden="true">/</span> 01</p><h2 id="studio-project-title">Safwa<br><em>Quran.</em></h2><p>A project centred on the Qur’an, reflection and daily practice. Currently in development.</p>{link('Explore the project','/quran.html')}</div>{book()}</section>
<section class="studio-outro wrap" aria-labelledby="studio-outro-title"><p class="eyebrow">From a thoughtful beginning.</p><h2 id="studio-outro-title">Meaningful ideas<br><em>start with a conversation.</em></h2>{link('Make a Studios enquiry','/connect.html?interest=studios')}<p class="social-follow">{link('Follow @safwa.studios',STUDIOS_INSTAGRAM,external=True)}</p></section>
'''

QURAN = f'''
<section class="inner-hero quran-hero wrap" aria-labelledby="quran-title"><div><p class="status">Project in development</p><p class="eyebrow gold">Safwa Quran</p><h1 id="quran-title">A quieter space.<br><em>A deeper<br>connection.</em></h1><p>A considered digital project centred on the Qur’an, reflection and daily practice.</p>{link('The intention behind it','#intention')}</div>{book()}</section>
<section id="intention" class="project-context wrap" aria-labelledby="intention-title"><div><p class="eyebrow gold">The intention</p><h2 id="intention-title">Faith, carried<br><em>into the everyday.</em></h2></div><div><p>Safwa Quran brings a digital expression to a familiar intention: making room for the Qur’an and reflection in everyday life.</p><p>The project is in development. Further details about the application and its availability will be shared as it progresses.</p><div class="notice">Downloads are not available through this website yet. You can contact Safwa Studios to ask about the project.</div></div></section>
<section class="faq-section wrap" aria-labelledby="quran-faq-title"><h2 id="quran-faq-title">A little<br><em>clarity.</em></h2><div><details><summary>Can I download the application?</summary><p>A public download is not available through this website yet. Availability will be announced as the project progresses.</p></details><details><summary>Where can I ask about Safwa Quran?</summary><p>Use the enquiry page to prepare a message about Safwa Quran, then send it to Safwa Studios on Instagram.</p></details><details><summary>When will more information be shared?</summary><p>Project updates and availability will be shared as development progresses. For enquiries, contact Safwa Studios.</p></details></div></section>
{contact_band()}
'''

CONNECT = f'''
<section class="contact-hero wrap" aria-labelledby="connect-title"><div><p class="eyebrow gold">Connect with The Safwa</p><h1 id="connect-title">A thoughtful<br><em>beginning.</em></h1></div><p>A question about learning, a creative idea, or an interest in Safwa Quran. Let’s find the right words.</p></section>
<section class="contact-layout wrap" aria-labelledby="enquiry-title"><div class="contact-details"><p class="eyebrow">Find your point of connection.</p><h2>One world.<br><em>Different conversations.</em></h2><p>Choose the part of Safwa you would like to reach.</p><div class="contact-channel"><h3>The Safwa</h3>{link('@thesafwa_',PARENT_INSTAGRAM,external=True)}</div><div class="contact-channel"><h3>Safwa Institute</h3>{link('@safwa.institute',INSTAGRAM,external=True)}</div><div class="contact-channel"><h3>Safwa Studios</h3>{link('@safwa.studios',STUDIOS_INSTAGRAM,external=True)}</div><div class="community-invite"><p class="eyebrow">A space to connect.</p>{link('Join the WhatsApp community',WHATSAPP_COMMUNITY,external=True)}<p class="small-note">Open the invitation on WhatsApp to view the community and choose whether to join.</p></div></div>
<form class="enquiry-form" aria-labelledby="enquiry-title"><h2 id="enquiry-title" class="eyebrow">Prepare your enquiry</h2><div class="form-field"><label for="name">Your name <span>(optional)</span></label><input id="name" name="name" autocomplete="name" maxlength="120" placeholder="How would you like to be addressed?"></div><div class="form-field"><label for="interest">What brings you here?</label><select id="interest" name="interest"><option value="general">General enquiries</option value="learning">Learning at Safwa</option><option value="admissions">Admissions and scholarships</option><option value="community">Community and updates</option><option value="studios">Safwa Studios</option><option value="quran">Safwa Quran</option></select></div><div class="form-field"><label for="message">Your message <span>(required)</span></label><textarea id="message" name="message" required minlength="5" maxlength="4000" placeholder="Tell Safwa a little about your question or idea."></textarea></div><div class="form-actions"><button type="submit" class="button">Copy message <span class="arrow" aria-hidden="true">↗</span></button><a id="enquiry-instagram" href="{PARENT_INSTAGRAM}" target="_blank" rel="noopener noreferrer" aria-label="Open Instagram for The Safwa (opens in a new tab)">Open Instagram<span class="visually-hidden"> (opens in a new tab)</span> ↗</a></div><p id="enquiry-destination" class="form-destination" aria-live="polite">Your message is for The Safwa (@thesafwa_).</p><p class="form-notice">This tool prepares text on your device. Copy it, then open Instagram to send your enquiry. Nothing is submitted or saved by this website. Please leave out confidential documents and sensitive personal information.</p><p class="form-feedback" role="status" aria-live="polite"></p><div id="copy-fallback" hidden><div class="form-field"><label for="ready-message">Your prepared message</label><textarea id="ready-message" readonly></textarea></div></div></form></section>
<section class="faq-section wrap" aria-labelledby="connect-faq-title"><h2 id="connect-faq-title">Before<br><em>you begin.</em></h2><div><details><summary>How do I ask about admissions or scholarships?</summary><p>Choose “Admissions and scholarships” in the enquiry tool and ask the Institute for current application dates, eligibility and submission instructions.</p></details><details><summary>Does this form send my message?</summary><p>It prepares a message for you to copy. Open the Instagram account selected for your enquiry, paste your message, and review it before sending.</p></details><details><summary>Can I upload application documents here?</summary><p>This website does not accept application documents. Ask the Institute for its approved submission process.</p></details></div></section>
'''

PAGES = [
    ('index.html','home','The Safwa — Excellence, Refined.','A considered world of faith, knowledge, creativity and purposeful growth. Discover Safwa Institute, Safwa Studios and Safwa Quran.',HOME,''),
    ('institute.html','institute','Safwa Institute — Faith, Knowledge & Growth','A space for Muslim women to deepen their faith, pursue meaningful knowledge, and grow into more intentional versions of themselves.',INSTITUTE,''),
    ('studios.html','studios','Safwa Studios — Media, Refined.','Discover Safwa Studios, its refined creative identity and the Safwa Quran digital project.',STUDIOS,'studio'),
    ('quran.html','quran','Safwa Quran — A Project in Development','Discover the intention behind Safwa Quran, a digital project centred on the Qur’an, reflection and daily practice.',QURAN,''),
    ('connect.html','connect','Connect with The Safwa','Prepare an enquiry about Safwa Institute, learning, admissions, community, Safwa Studios or Safwa Quran.',CONNECT,''),
]

def main():
    for filename, current, title, description, content, theme in PAGES:
        canonical = WEBSITE_ORIGIN + ('/' if filename == 'index.html' else '/' + filename)
        html = f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{escape(title)}</title><meta name="description" content="{escape(description)}"><meta name="theme-color" content="{'#102c24' if theme else '#f7f4ed'}"><meta name="robots" content="index,follow"><link rel="canonical" href="{canonical}"><meta property="og:type" content="website"><meta property="og:title" content="{escape(title)}"><meta property="og:description" content="{escape(description)}"><meta property="og:url" content="{canonical}"><meta property="og:image" content="{WEBSITE_ORIGIN}/assets/the-safwa-logo.jpg"><meta http-equiv="Content-Security-Policy" content="default-src 'self'; img-src 'self' data:; font-src 'self'; script-src 'self'; style-src 'self'; object-src 'none'; base-uri 'self'; form-action 'none'"><meta name="referrer" content="strict-origin-when-cross-origin"><link rel="icon" href="/assets/the-safwa-logo.jpg" type="image/jpeg"><link rel="preload" href="/assets/fonts/cormorant-garamond.woff" as="font" type="font/woff" crossorigin><link rel="stylesheet" href="/experience.css"><script src="/app.js" defer></script></head><body data-theme="{theme}" data-page="{current}">{header(current)}<main id="main">{content}</main>{footer()}</body></html>'''
        (DIST / filename).write_text(html,encoding='utf-8')
        print(f'Built {filename}')
    (DIST/'robots.txt').write_text(f'User-agent: *\nAllow: /\nSitemap: {WEBSITE_ORIGIN}/sitemap.xml\n')
    urls = [WEBSITE_ORIGIN + ('/' if page[0] == 'index.html' else '/' + page[0]) for page in PAGES]
    sitemap = '<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">' + ''.join(f'<url><loc>{url}</loc></url>' for url in urls) + '</urlset>\n'
    (DIST/'sitemap.xml').write_text(sitemap)

if __name__ == '__main__':
    main()
