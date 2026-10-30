(() => {
  'use strict';
  const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
  if (!reducedMotion.matches) document.documentElement.classList.add('js-motion');

  const menuButton = document.querySelector('.menu-toggle');
  const menu = document.querySelector('.mobile-nav');
  const setMenu = (open, returnFocus = false) => {
    menuButton?.setAttribute('aria-expanded', String(open));
    menuButton?.setAttribute('aria-label', open ? 'Close navigation menu' : 'Open navigation menu');
    menu?.classList.toggle('open', open);
    document.body.classList.toggle('menu-open', open);
    document.querySelector('main').inert = open;
    document.querySelector('footer').inert = open;
    if (menu) menu.inert = !open;
    if (open) menu?.querySelector('a')?.focus();
    else if (returnFocus) menuButton?.focus();
  };
  if (menu) menu.inert = true;
  menuButton?.addEventListener('click', () => setMenu(menuButton.getAttribute('aria-expanded') !== 'true'));
  menu?.addEventListener('click', event => {
    if (event.target.closest('a')) setMenu(false);
  });
  document.addEventListener('keydown', event => {
    if (!document.body.classList.contains('menu-open')) return;
    if (event.key === 'Escape') { setMenu(false, true); return; }
    if (event.key !== 'Tab') return;
    const targets = [menuButton, ...menu.querySelectorAll('a')];
    const index = targets.indexOf(document.activeElement);
    if (event.shiftKey && index <= 0) { event.preventDefault(); targets.at(-1)?.focus(); }
    if (!event.shiftKey && index === targets.length - 1) { event.preventDefault(); menuButton?.focus(); }
  });
  const compact = window.matchMedia('(max-width: 800px)');
  compact.addEventListener('change', () => { if (!compact.matches) setMenu(false); });

  const tabs = [...document.querySelectorAll('[data-purpose-tab]')];
  function selectPurpose(tab) {
    tabs.forEach(item => {
      const selected = item === tab;
      item.setAttribute('aria-selected', String(selected));
      item.tabIndex = selected ? 0 : -1;
      const panel = document.getElementById(item.getAttribute('aria-controls'));
      if (panel) panel.hidden = !selected;
    });
  }
  tabs.forEach((tab, index) => {
    tab.addEventListener('click', () => selectPurpose(tab));
    tab.addEventListener('keydown', event => {
      let target;
      if (event.key === 'ArrowRight') target = (index + 1) % tabs.length;
      if (event.key === 'ArrowLeft') target = (index - 1 + tabs.length) % tabs.length;
      if (event.key === 'Home') target = 0;
      if (event.key === 'End') target = tabs.length - 1;
      if (target === undefined) return;
      event.preventDefault(); selectPurpose(tabs[target]); tabs[target].focus();
    });
  });
  if (tabs.length) selectPurpose(tabs[0]);

  const form = document.querySelector('.enquiry-form');
  const feedback = document.querySelector('.form-feedback');
  const interest = form?.querySelector('#interest');
  const destinations = {
    general: { name: 'The Safwa', handle: '@thesafwa_', url: 'https://www.instagram.com/thesafwa_/' },
    studios: { name: 'Safwa Studios', handle: '@safwa.studios', url: 'https://www.instagram.com/safwa.studios/' },
    quran: { name: 'Safwa Studios', handle: '@safwa.studios', url: 'https://www.instagram.com/safwa.studios/' },
    institute: { name: 'Safwa Institute', handle: '@safwa.institute', url: 'https://www.instagram.com/safwa.institute/' }
  };
  const destinationFor = value => destinations[value] || destinations.institute;
  const chosen = new URLSearchParams(window.location.search).get('interest');
  if (interest && [...interest.options].some(option => option.value === chosen)) interest.value = chosen;
  const updateDestination = () => {
    if (!interest) return;
    const destination = destinationFor(interest.value);
    const accountLink = document.querySelector('#enquiry-instagram');
    accountLink.href = destination.url;
    accountLink.setAttribute('aria-label', `Open Instagram for ${destination.name} (opens in a new tab)`);
    document.querySelector('#enquiry-destination').textContent = `Your message is for ${destination.name} (${destination.handle}).`;
    feedback.textContent = '';
    document.querySelector('#copy-fallback').hidden = true;
  };
  interest?.addEventListener('change', updateDestination);
  updateDestination();
  form?.addEventListener('submit', async event => {
    event.preventDefault();
    if (!form.reportValidity()) return;
    const name = form.querySelector('#name').value.trim();
    const message = form.querySelector('#message').value.trim();
    if (!message) { feedback.textContent = 'Please add a message before copying your enquiry.'; return; }
    const topic = interest.selectedOptions[0].textContent;
    const destination = destinationFor(interest.value);
    const text = `Assalamu alaikum, ${destination.name}.\n\n${name ? `My name is ${name}.\n` : ''}I’m getting in touch about ${topic.toLowerCase()}.\n\n${message}`;
    try {
      if (!navigator.clipboard?.writeText) throw new Error('Clipboard not available');
      await navigator.clipboard.writeText(text);
      feedback.textContent = `Message copied. Open Instagram, paste it into a message to ${destination.handle}, and send when you’re ready.`;
    } catch {
      const fallback = document.querySelector('#copy-fallback');
      fallback.hidden = false;
      fallback.querySelector('textarea').value = text;
      fallback.querySelector('textarea').focus();
      fallback.querySelector('textarea').select();
      feedback.textContent = 'Your message is ready below. Select and copy it, then open Instagram to send it.';
    }
  });

  const privacy = document.querySelector('.privacy-dialog');
  document.querySelector('[data-open-privacy]')?.addEventListener('click', () => privacy?.showModal());
  document.querySelector('[data-close-privacy]')?.addEventListener('click', () => privacy?.close());
  privacy?.addEventListener('click', event => {
    if (event.target !== privacy) return;
    const box = privacy.getBoundingClientRect();
    if (event.clientX < box.left || event.clientX > box.right || event.clientY < box.top || event.clientY > box.bottom) privacy.close();
  });
})();
