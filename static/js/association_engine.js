// association_engine.js — offline word-association question delivery
// Loads bank JSON from /static/data/, shuffles options, tracks used IDs.

'use strict';
(function (root, factory) {
  if (typeof module !== 'undefined') module.exports = factory(require('./rng.js'));
  else root.AssocE = factory({ RNG });
}(typeof globalThis !== 'undefined' ? globalThis : this, function (rngMod) {

const _cache = {};  // language → loaded bank array

async function loadBank(language) {
  if (_cache[language]) return _cache[language];
  const url = `/static/data/associations_${language}.json`;
  const resp = await fetch(url);
  if (!resp.ok) throw new Error(`Failed to load association bank: ${url}`);
  const bank = await resp.json();
  _cache[language] = bank;
  return bank;
}

function getQuestion(bank, rng, excludeIds) {
  let available = bank.filter(q => !excludeIds.includes(q.id));
  if (available.length === 0) available = bank.slice(); // reset when exhausted
  const q = rng.choice(available);

  // Build shuffled options: correct answer + 3 distractors
  const options = [q.answer].concat((q.distractors || []).slice(0, 3));
  // Ensure exactly 4 options (pad with em-dash if somehow fewer), mirroring
  // association_engine.py's _attach_options()
  while (options.length < 4) options.push('—');
  rng.shuffle(options);

  return {
    id:          q.id,
    prompt_a1:   q.prompt_a1,
    prompt_a2:   q.prompt_a2,
    prompt_b1:   q.prompt_b1,
    answer:      q.answer,
    category:    q.category,
    relationship: q.relationship || '',
    options,
    correct_index: options.indexOf(q.answer),
  };
}

return { loadBank, getQuestion };

}));
