// Helper da automação pela tela do currículo (roteiro 04). Roda dentro da página
// http://localhost:3000/portuguese-version/como-estou-indo/ver-meu-curriculo, colado no console ou injetado pelo
// navegador automatizado: preenche os campos pelos eventos que o React escuta e clica nos botões de verdade (Avançar,
// Salvar dados, Inativar, Reativar, Excluir e as confirmações), então cada requisição sai do código do front.
// A amostra (sessões e currículos) vem de http://127.0.0.1:3999/ (07-amostra-para-tela.mjs + servidor local), e cada
// verificação é enviada por POST para o mesmo endereço, que a grava em resultados-tela.jsonl.
window.T = {
    sleep: (ms) => new Promise((r) => setTimeout(r, ms)),
    // ids das regiões na ordem em que o MultiSelect as mostra (RegioesComponent): 0 = qualquer cidade, 10 = home office
    regionIds: ['0', '10', '11', '12', '13', '14', '15', '16', '17', '18', '19', '21', '22', '24', '27', '28', '31', '32', '33', '34', '35', '37', '38', '41', '42', '43', '44', '45', '46', '47', '48', '49', '51', '53', '54', '55', '61', '62', '63', '64', '65', '66', '67', '68', '69', '71', '73', '74', '75', '77', '79', '81', '82', '83', '84', '85', '86', '87', '88', '89', '91', '92', '93', '94', '95', '96', '97', '98', '99'],
    setValue(el, value) {
        const proto = el.tagName === 'TEXTAREA' ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
        Object.getOwnPropertyDescriptor(proto, 'value').set.call(el, String(value));
        el.dispatchEvent(new Event('input', { bubbles: true }));
        el.dispatchEvent(new Event('change', { bubbles: true }));
    },
    async waitFor(fn, ms = 20000) {
        const started = Date.now();
        while (Date.now() - started < ms) {
            const value = fn();
            if (value) return value;
            await T.sleep(100);
        }
        return null;
    },
    card: () => document.querySelector('.card'),
    // só o texto da faixa: desde 2026-10-15 ela também leva os botões Inativar / Reativar / Excluir
    status: () => (document.querySelector('.resume-status span') || document.querySelector('.resume-status') || {}).innerText || '',
    button: (text) => [...document.querySelectorAll('button')].find((b) => b.innerText.trim() === text),
    nextButton() {
        const buttons = [...T.card().querySelectorAll('button')].filter((b) => b.innerText.trim());
        return buttons[buttons.length - 1];
    },
    toasts: () => [...document.querySelectorAll('.p-toast-message')].map((t) => t.innerText.replace(/\s+/g, ' ').trim()),
    // os avisos de pendência que a tela mostra embaixo, ao lado do botão de avançar
    pending: () => [...T.card().querySelectorAll('li, .p-error, .text-danger, small')].map((e) => e.innerText.trim()).filter(Boolean),
    async chooseDropdown(element, index) {
        for (let i = 0; i < 3 && !document.querySelector('.p-dropdown-item'); i++) {
            element.click();
            await T.sleep(400);
        }
        const items = [...document.querySelectorAll('.p-dropdown-item')];
        items[index] && items[index].click();
        await T.sleep(300);
    },
    async addCompany(text, pickSuggestion) {
        const input = document.querySelector('#notAllowedCompany input') || document.querySelector('#notAllowedCompany');
        input.focus();
        T.setValue(input, text);
        if (pickSuggestion) {
            const item = await T.waitFor(() => document.querySelector('.p-autocomplete-item'), 6000);
            if (!item) return { autocomplete: text, picked: null };
            const label = item.innerText;
            const suggestions = [...document.querySelectorAll('.p-autocomplete-item')].map((li) => li.innerText);
            item.click();
            await T.sleep(300);
            // a tela recusa empresa com mais de 50 caracteres (eram 20 até 2026-10-15: achado 23)
            const tooLong = suggestions.filter((suggestion) => suggestion.length > 50);
            if (label.length > 50) {
                const tokens = [...document.querySelectorAll('#notAllowedCompany .p-autocomplete-token')];
                const token = tokens.find((t) => t.innerText.trim() === label);
                token && token.querySelector('.p-autocomplete-token-icon').dispatchEvent(new MouseEvent('click', { bubbles: true }));
                await T.sleep(300);
            }
            return { autocomplete: text, picked: label, suggestions: suggestions.length, tooLong };
        }
        input.dispatchEvent(new KeyboardEvent('keyup', { key: 'Enter', bubbles: true }));
        await T.sleep(300);
        return { typed: text };
    },
    async fillResumeTab(item, index) {
        const r = item.resume;
        T.setValue(document.querySelector('#desiredJob'), r.desiredJob || '');
        T.setValue(document.querySelector('#lastJob'), r.lastJob || '');
        T.setValue(document.querySelector('#linkedinAddress'), r.linkedinAddress);
        await T.chooseDropdown(document.querySelector('#resumeType'), r.resumeType - 1);
        if (r.resumeType === 1) {
            const textArea = await T.waitFor(() => document.querySelector('#resumeText'));
            T.setValue(textArea, item.resumeText);
        }
        // empresas: uma pelo autocomplete (companies/search/autocomplete) e uma digitada, em parte da amostra
        const companies = [];
        if (index % 3 === 0) companies.push(await T.addCompany(['Ita', 'Bra', 'San', 'Glo'][index % 4], true));
        if (index % 4 === 1) companies.push(await T.addCompany('Consultoria Teste', false));
        return companies;
    },
    async fillLanguages(languages) {
        const card = T.card();
        const checkbox = card.querySelector('#doNotSpeakAnyLanguage input') || card.querySelector('input.p-checkbox-input');
        const wanted = languages.length > 0;
        if (checkbox.checked !== wanted) {
            checkbox.click();
            await T.sleep(500);
        }
        if (!wanted) return [];
        const multiSelect = await T.waitFor(() => card.querySelector('.p-multiselect'));
        multiSelect.click();
        await T.sleep(500);
        const notFound = [];
        for (const language of languages) {
            const item = [...document.querySelectorAll('.p-multiselect-item')].find((li) => li.innerText.trim() === language.name);
            if (!item) {
                notFound.push(language.name);
                continue;
            }
            item.getAttribute('aria-selected') !== 'true' && item.click();
            await T.sleep(150);
        }
        document.body.click();
        await T.sleep(400);
        const found = languages.filter((language) => !notFound.includes(language.name));
        const levelDropdowns = [...card.querySelectorAll('.p-dropdown')];
        for (let i = 0; i < found.length && i < levelDropdowns.length; i++) {
            await T.chooseDropdown(levelDropdowns[i], found[i].level - 1);
        }
        return notFound;
    },
    checkboxRow: (label) => [...T.card().querySelectorAll('.p-checkbox')].find((c) => c.parentElement.innerText.trim().startsWith(label)),
    async setCheckbox(label, checked) {
        const row = T.checkboxRow(label);
        const input = row.querySelector('input');
        if (input.checked !== checked) {
            input.click();
            await T.sleep(200);
        }
    },
    // IntegerFieldComponent: o checkbox marcado vale 0; desmarcado aparece o campo, cujo id é o rótulo dele
    async setInteger(checkLabel, textLabel, value) {
        await T.setCheckbox(checkLabel, Number(value) === 0);
        if (Number(value) === 0) return;
        const input = await T.waitFor(() => document.getElementById(textLabel), 3000);
        T.setValue(input, value);
        await T.sleep(150);
    },
    async fillOptions(r) {
        const multiSelect = T.card().querySelector('.p-multiselect');
        multiSelect.click();
        await T.sleep(500);
        const items = () => [...document.querySelectorAll('.p-multiselect-item')];
        const isSelected = (li) => li.getAttribute('aria-selected') === 'true';
        // limpa a seleção (a opção 0, "qualquer cidade", marca e desmarca todas de uma vez)
        for (let i = 0; i < 80 && items().some(isSelected); i++) {
            const first = items().find(isSelected);
            first.click();
            await T.sleep(60);
        }
        const wanted = (r.ddd || []).map(String);
        const allMetropolitan = wanted.length === 67 && !wanted.includes('10');
        const toClick = allMetropolitan ? ['0'] : wanted;
        for (const id of toClick) {
            const li = items()[T.regionIds.indexOf(id)];
            li && !isSelected(li) && li.click();
            await T.sleep(60);
        }
        document.body.click();
        await T.sleep(400);
        await T.setCheckbox('Possuo necessidades especiais', !!r.pcd);
        await T.setCheckbox('Tenho disponibilidade para viagens', !!r.travel);
        await T.setInteger('Estou pleiteando meu primeiro emprego', 'Anos de experiência', r.experience || 0);
        await T.setInteger('Tenho disponibilidade imediata', 'Dias necessários para engajar em um novo emprego', r.disponibility || 0);
        await T.setInteger('Não aceito empregos temporários', 'Total mínimo de duração (em meses) do emprego temporário que eu aceitaria', r.temporallyJobTime || 0);
    },
    async fillSalary(r) {
        await T.setInteger('Não aceito empregos CLT', 'Minha pretensão salarial mensal CLT (número inteiro em reais)', r.clt || 0);
        await T.setInteger('Não aceito empregos PJ', 'Minha pretensão salarial mensal PJ (número inteiro em reais)', r.pj || 0);
        await T.setInteger('Não aceito eventuais freelancers em bitcoin', 'Minha pretensão em bitcoin (Valor equivalente em reais)', r.btc || 0);
        await T.setCheckbox('Minhas pretensões salariais são negociáveis', !!r.negotiableClaim);
    },
    // avança uma aba e espera o rótulo do botão mudar (a aba de habilidades depende do skills/fromText)
    async advance() {
        const before = T.nextButton().innerText.trim();
        const pendingBefore = T.pending();
        T.nextButton().click();
        const changed = await T.waitFor(() => T.nextButton() && T.nextButton().innerText.trim() !== before, 30000);
        return changed ? null : { stuckAt: before, pending: T.pending().filter((p) => !pendingBefore.includes(p)).concat(pendingBefore) };
    },
    async fillAndSave(item, index) {
        const started = Date.now();
        const result = { email: item.email, kind: item.kind, resumeType: item.resume.resumeType, step: 'preencher' };
        result.companies = await T.fillResumeTab(item, index);
        let stuck = await T.advance();
        if (stuck) return { ...result, step: 'aba Currículo', stuck };
        result.languagesNotFound = await T.fillLanguages(item.resume.spokenLanguage || []);
        stuck = await T.advance();
        if (stuck) return { ...result, step: 'aba Idiomas', stuck };
        if (T.nextButton().innerText.trim() === 'Opções') {
            result.skillsTab = T.card().innerText.match(/(\d+) Habilidades/)?.[1];
            stuck = await T.advance();
            if (stuck) return { ...result, step: 'aba Habilidades', stuck };
        }
        await T.fillOptions(item.resume);
        stuck = await T.advance();
        if (stuck) return { ...result, step: 'aba Opções', stuck };
        await T.fillSalary(item.resume);
        // o currículo já gravado já mostra "ativo" antes de salvar: o que vale é o toast do salvamento (ou um de erro)
        document.querySelectorAll('.p-toast-message-icon, .p-toast-icon-close').forEach((close) => close.closest('button') && close.closest('button').click());
        const saveStarted = Date.now();
        T.button('Salvar dados').click();
        const outcome = await T.waitFor(() => T.toasts().find((t) => /salvo com sucesso|erro|falha|inválid|não/i.test(t)), 120000);
        const saved = !!outcome && /salvo com sucesso/.test(outcome) && T.status().startsWith('Currículo ativo');
        return { ...result, step: 'salvar', saved, outcome, toasts: T.toasts(), status: T.status(), saveMs: Date.now() - saveStarted, ms: Date.now() - started, timedOut: !outcome };
    },
    // confere, depois de recarregar a tela, o que o GET /resume devolveu para os campos visíveis
    readForm() {
        const multiSelectLabel = (T.card().querySelector('.p-multiselect-label') || {}).innerText || '';
        return {
            status: T.status(),
            desiredJob: (document.querySelector('#desiredJob') || {}).value,
            lastJob: (document.querySelector('#lastJob') || {}).value,
            linkedinAddress: (document.querySelector('#linkedinAddress') || {}).value,
            resumeType: ((document.querySelector('#resumeType') || {}).innerText || '').slice(0, 25),
            companies: [...document.querySelectorAll('#notAllowedCompany .p-autocomplete-token-label')].map((e) => e.innerText),
            firstTabMultiSelect: multiSelectLabel,
        };
    },
    async confirm(acceptLabel) {
        const accept = await T.waitFor(() => T.button(acceptLabel), 5000);
        if (!accept) return false;
        accept.click();
        return true;
    },
    // Inativar, Reativar e Excluir ficam na faixa de situação, em todas as abas (até 2026-10-15 só ao lado do
    // "Salvar dados", na última aba, e o ciclo de vida precisava avançar até ela)
    async lifecycle(kind) {
        const steps = [];
        const act = async (buttonText, acceptLabel, expectedStatus) => {
            const button = T.button(buttonText);
            if (!button) return steps.push({ action: buttonText, error: 'botão ausente', status: T.status() });
            button.click();
            const confirmed = await T.confirm(acceptLabel);
            const reached = await T.waitFor(() => T.status().startsWith(expectedStatus), 60000);
            steps.push({ action: buttonText, confirmed, status: T.status(), ok: !!reached, toasts: T.toasts() });
        };
        if (kind === 'inativar-reativar') {
            await act('Inativar', 'Sim, inativar', 'Currículo inativo');
            await act('Reativar', 'Sim, reativar', 'Currículo ativo');
        }
        if (kind === 'excluir') {
            await act('Excluir', 'Sim, excluir', 'Você ainda não tem');
            steps.push({ formAfterDelete: T.readForm() });
        }
        if (kind === 'inativar-excluir') {
            await act('Inativar', 'Sim, inativar', 'Currículo inativo');
            await act('Excluir', 'Sim, excluir', 'Você ainda não tem');
        }
        return steps;
    },
    // ciclo de vida aplicado a cada candidato da amostra, pelo índice
    lifecycleOf: (index) => (index % 3 === 0 ? 'inativar-reativar' : index % 6 === 1 ? 'excluir' : index % 6 === 4 ? 'inativar-excluir' : 'nenhum'),
    // passo A: confere o que a tela recarregou (GET /resume) do candidato salvo no passo B, roda o ciclo de vida e troca
    // para o próximo candidato
    async stepA(index) {
        const sample = await T.loadSample();
        if (index > 0) {
            const previous = sample[index - 1];
            await T.waitFor(() => T.status(), 20000);
            await T.waitFor(() => (document.querySelector('#linkedinAddress') || {}).value, 10000);
            const form = T.readForm();
            const r = previous.resume;
            const differences = [];
            form.desiredJob !== (r.desiredJob || '') && differences.push(`desiredJob: tela '${form.desiredJob}' x enviado '${r.desiredJob}'`);
            form.lastJob !== (r.lastJob || '') && differences.push(`lastJob: tela '${form.lastJob}' x enviado '${r.lastJob}'`);
            form.linkedinAddress !== r.linkedinAddress && differences.push(`linkedin: tela '${form.linkedinAddress}' x enviado '${r.linkedinAddress}'`);
            !form.status.startsWith('Currículo ativo') && differences.push(`situação: '${form.status}'`);
            const kind = T.lifecycleOf(index - 1);
            const lifecycle = kind === 'nenhum' ? [] : await T.lifecycle(kind);
            await T.record({ step: 'recarga', email: previous.email, index: index - 1, form, differences, lifecycleKind: kind, lifecycle });
        }
        if (index < sample.length) T.switchTo(sample[index]);
        return index < sample.length ? sample[index].email : 'fim';
    },
    // passo B: preenche as abas, salva e recarrega a tela para o passo A conferir
    async stepB(index) {
        const sample = await T.loadSample();
        await T.waitFor(() => T.status(), 20000);
        const statusBefore = T.status();
        const result = await T.fillAndSave(sample[index], index);
        await T.record({ ...result, index, statusBefore });
        result.saved && location.reload();
        return result;
    },
    record: (result) => fetch('http://127.0.0.1:3999/', { method: 'POST', body: JSON.stringify(result) }),
    async loadSample() {
        window.__amostra = window.__amostra || (await fetch('http://127.0.0.1:3999/').then((r) => r.json()));
        return window.__amostra;
    },
    // troca o candidato da aba: a sessão fica no sessionStorage, como o modal de login deixa
    switchTo(item) {
        sessionStorage.setItem('login', JSON.stringify({ email: item.email, sessionToken: item.sessionToken }));
        localStorage.removeItem('logins');
        location.reload();
    },
};
