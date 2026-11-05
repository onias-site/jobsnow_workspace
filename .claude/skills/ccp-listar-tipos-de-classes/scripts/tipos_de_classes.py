"""Classifica cada tipo Java de produção do workspace numa única categoria e imprime a contagem.

Uso:
  python -X utf8 tipos_de_classes.py                    # grade com categoria, quantidade e porcentagem
  python -X utf8 tipos_de_classes.py --detalhe Fields   # lista os tipos de uma categoria (parte do nome basta)
  python -X utf8 tipos_de_classes.py --conflitos        # tipos que atendem mais de uma categoria e quem venceu
  python -X utf8 tipos_de_classes.py --tsv saida.tsv    # grava categoria, módulo, tipo e espécie

Escopo: src/main de todos os módulos, menos ccp_rest-api-tests_jobsnow, documentation, o front end e target.
Um tipo por arquivo (o tipo cujo nome é o do arquivo). Cada tipo conta para uma única categoria: a
primeira regra de CRITERIOS que ele atende.
"""
import argparse
import collections
import os
import re
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), *[os.pardir] * 4))
SKIP_DIRS = {'documentation', 'target', '.git', 'node_modules', 'bin', '.settings', '.metadata'}
SKIP_MODULES = {'ccp_rest-api-tests_jobsnow', 'jn_frontend_calistrato-react'}
MAIN = os.sep + 'src' + os.sep + 'main' + os.sep

DECL = re.compile(r'^(?:public\s+|abstract\s+|final\s+|sealed\s+|non-sealed\s+|privileged\s+|strictfp\s+)*'
                  r'(class|interface|enum|@interface|record|aspect)\s+(\w+)(.*?)\{', re.S | re.M)
EXCEPTION_ROOTS = {'RuntimeException', 'Exception', 'Error', 'Throwable', 'IllegalStateException',
                   'IllegalArgumentException'}

# ---- listas nominais (categorias que não se reconhecem por supertipo) -------------------------------
DSL = re.compile(r'^(?!CcpQueryExecutor)(CcpQuery\w*|BucketAggregation|CcpSelect\w*|CcpGetEntityId|CcpTreeFlow|'
                 r'CcpAndIfThisExecutionReturns|CcpBeginThisStatement|CcpExecuteTheGivenProcess|'
                 r'CcpIfThisExecutionReturns|CcpTryToExecuteTheGivenFinalTargetProcess|CcpUsingTheGivenJson|'
                 r'JnAddDefaultStep|JnAndWithThe\w+|JnCreateStep|JnSoWithAllAddedStepsAnd|JnWithTheProcess|'
                 r'JnWithTheTemplateId|Builder)$')
ENGINE = set('CcpDependencyInjection CcpEntityFactory CcpEntityMetaData CcpEntityDataMover '
             'CcpJsonFieldDefaultValuesEngine CcpJsonValidationRulesEngine CcpJsonValidatorEngine CcpCachedService '
             'CcpMensageriaReceiver JnMensageriaReceiver JbBotEngine BotChatLanguage PendingTicket CcpToStringBuilder '
             'CcpHttpHandler CcpHttpResponse CcpHttpBodyBinary CcpHttpBodyText CcpHttpSecretMask BulkItem '
             'JnBulkCreateResult JnEntityGrouperParents'.split())
WEB = set('CcpJsonServletInputStream CcpRawServletInputStream CcpMissingPathParamsCustomizer '
          'CcpPutSessionValuesAndExecuteTaskFilter CcpPutSessionValuesRequestWrapper CcpValidEmailFilter '
          'CcpRestApiUtils CcpMessageReceiver CcpPubSubStarter CcpPubSubTopicConsumer GcpPubSubSdkPublishing '
          'GcpPubSubPublishing CcpJsonExtractorFromHttpServletRequest AsyncMensageriaProcessRun '
          'CcpLocalMensageriaRunningMarks CcpHttpRequestRetryHandler JbInstantMessengerDependencyChooser '
          'JbInstantMessengerMessageReader CcpRestApiExceptionHandlerSpring CcpRestApiSessionValuesRemoverSpring '
          'JsRestApiPrivacyPolicyCacheHeader VisRestApiSkillStatisticsCacheHeader'.split())
UTIL = set('CacheDeletionMarks JnEmailHtml VisEmailHtml JnMessages VisMessages JnGroupers JnSystemProperties '
           'JsTelegramWebhookSecret JsContactUsMessageValues VisRecruiterDomainGroups VisResumeEmails '
           'VisResumeLinkedinEmails VisSkillDictionary VisSkillDictionarySnapshot VisSkillWordsByInitials '
           'VisSkillsInText VisTelegramContact VisTelegramDdd VisTelegramMessages VisTelegramPositionText '
           'VisTelegramPositionsIndex VisTelegramSeniority VisWhatsAppMessages CcpOtherConstants'.split())
ENTITY_INFRA = {'CcpBulkItem'}
BOT = re.compile(r'(BotConfiguration|Conversation|^JsSupportContactUsAnswer|^VisSupportSkillFixHierarchyAnswer|'
                 r'^JnBotConfigurationSeeds|^JbSupportPendingTicketsList|^JnSupportIgnoredUsersList|ReviewMessage|'
                 r'BotCommands|Steps|AnswerType)$')


def strip_generics(text):
    out, depth = [], 0
    for ch in text:
        if ch == '<':
            depth += 1
        elif ch == '>':
            depth -= 1
        elif depth == 0:
            out.append(ch)
    return ''.join(out)


def read_types():
    types = {}
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        rel = os.path.relpath(dirpath, ROOT)
        module = rel.split(os.sep)[0]
        if module in SKIP_MODULES or MAIN not in dirpath + os.sep:
            continue
        for filename in filenames:
            if not filename.endswith(('.java', '.aj')) or filename in ('package-info.java', 'module-info.java'):
                continue
            path = os.path.join(dirpath, filename)
            source = open(path, encoding='utf-8', errors='replace').read()
            code = re.sub(r'/\*.*?\*/', '', source, flags=re.S)
            code = re.sub(r'//[^\n]*', '', code)
            base = filename.rsplit('.', 1)[0]
            matches = list(DECL.finditer(code))
            if not matches:
                print('NAO RECONHECIDO:', path, file=sys.stderr)
                continue
            match = next((m for m in matches if m.group(2) == base), matches[0])
            kind, name, rest = match.group(1), match.group(2), strip_generics(match.group(3))
            supers = []
            ext = re.search(r'extends\s+([\w\s,.]+?)(?=implements|$)', rest, re.S)
            if ext:
                supers += [s.strip().split('.')[-1] for s in ext.group(1).split(',') if s.strip()]
            imp = re.search(r'implements\s+([\w\s,.]+)', rest, re.S)
            if imp:
                supers += [s.strip().split('.')[-1] for s in imp.group(1).split(',') if s.strip()]
            package = re.search(r'package\s+([\w.]+)', code)
            types[name] = dict(name=name, kind=kind, supers=supers, pkg=package.group(1) if package else '',
                               module=module, src=code, head=code[:match.start()],
                               entity=bool(re.search(r'static\s+final\s+CcpEntity\s+ENTITY|final\s+static\s+CcpEntity\s+ENTITY', code)))
    return types


def build_criteria(types):
    def reaches(name, target, seen=None):
        seen = seen if seen is not None else set()
        if name == target:
            return True
        if name in seen or name not in types:
            return False
        seen.add(name)
        return any(reaches(s, target, seen) for s in types[name]['supers'])

    def is_exception(name, seen=None):
        seen = seen if seen is not None else set()
        if name in EXCEPTION_ROOTS:
            return True
        if name in seen or name not in types:
            return False
        seen.add(name)
        return any(is_exception(s, seen) for s in types[name]['supers'])

    specs = {n for n, i in types.items() if i['pkg'].startswith('com.ccp.especifications') and i['kind'] == 'interface'}

    def is_spec(name):
        return name in specs or any(reaches(name, s) for s in specs)

    def ignored(n, i):
        return (i['kind'] == 'aspect' or 'OpenApi' in n
                or bool(re.search(r'@(RestController|SpringBootApplication|Configuration)\b', i['head']))
                or bool(re.search(r'public\s+static\s+void\s+main\s*\(', i['src'])))

    def schema(n, i):
        body = i['src'].split('{', 1)[1]
        return (i['kind'] == 'class' and not i['supers']
                and bool(re.search(r'@CcpJson(FieldValidator|CopyFieldValidations)', i['src']))
                and not re.search(r'\(\s*[^)]*\)\s*\{', body))

    def decorator(n, i):
        return (reaches(n, 'CcpDecorator') or n.endswith('Decorator') or n == 'AlreadyTransformedJson'
                or (i['pkg'] == 'com.ccp.decorators' and not i['supers'] and i['kind'] == 'class'))

    return [
        ('Entidades de dados', lambda n, i: i['entity']),
        ('Business', lambda n, i: reaches(n, 'CcpBusiness')),
        ('Infraestrutura para entidades de dados', lambda n, i: reaches(n, 'CcpEntity') or n in ENTITY_INFRA),
        ('DSLs fluentes', lambda n, i: bool(DSL.match(n))),
        ('Motores e infraestrutura do framework', lambda n, i: n in ENGINE),
        ('Infraestrutura web e de mensageria', lambda n, i: n in WEB),
        ('Utilitários e estado em memória', lambda n, i: n in UTIL),
        ('Configuração e conversa do bot', lambda n, i: bool(BOT.search(n))),
        ('Decorators', decorator),
        ('Anotações', lambda n, i: i['kind'] == '@interface'),
        ('Exceções', lambda n, i: is_exception(n)),
        ('Provedores de DI', lambda n, i: reaches(n, 'CcpInstanceProvider')),
        ('Especificação / implementação', lambda n, i: is_spec(n)),
        ('Fields', lambda n, i: reaches(n, 'CcpJsonFieldName')),
        ('Ignorados (aspectos e pontos de entrada)', ignored),
        ('Enum complexo', lambda n, i: i['kind'] == 'enum' and bool(i['supers'])),
        ('Enum simples', lambda n, i: i['kind'] == 'enum' and not i['supers']),
        ('Esquemas de validação de entrada', schema),
        ('Outras interfaces', lambda n, i: i['kind'] == 'interface' or bool(i['supers'])),
    ]


def grid(headers, rows, right):
    widths = [max(len(str(x)) for x in col) for col in zip(headers, *rows)]

    def line(left, mid, end):
        return left + mid.join('─' * (w + 2) for w in widths) + end

    def fmt(row):
        cells = [(' ' + str(v).rjust(w) + ' ') if c in right else (' ' + str(v).ljust(w) + ' ')
                 for c, (v, w) in enumerate(zip(row, widths))]
        return '│' + '│'.join(cells) + '│'
    out = [line('┌', '┬', '┐'), fmt(headers), line('├', '┼', '┤')]
    out += [fmt(r) for r in rows[:-1]] + [line('├', '┼', '┤'), fmt(rows[-1]), line('└', '┴', '┘')]
    return '\n'.join(out)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--detalhe')
    parser.add_argument('--conflitos', action='store_true')
    parser.add_argument('--tsv')
    args = parser.parse_args()

    types = read_types()
    criteria = build_criteria(types)
    result, overlaps = [], []
    for name, info in types.items():
        hits = [cat for cat, rule in criteria if rule(name, info)]
        if not hits:
            hits = ['SEM CATEGORIA']
        result.append((hits[0], info['module'], name, info['kind']))
        # "Outras interfaces" é a categoria de sobra; coincidir com ela não é conflito
        real = [h for h in hits if h != 'Outras interfaces']
        if len(real) > 1:
            overlaps.append((name, real))

    counts = collections.Counter(r[0] for r in result)
    total = sum(counts.values())

    if args.tsv:
        with open(args.tsv, 'w', encoding='utf-8') as out:
            out.write(''.join('\t'.join(r) + '\n' for r in sorted(result)))

    if args.detalhe:
        wanted = [c for c in counts if args.detalhe.lower() in c.lower()]
        for cat in wanted:
            members = sorted((r[1], r[2], r[3]) for r in result if r[0] == cat)
            print(f'{cat} ({len(members)})')
            rows = [(i + 1, m[0], m[1], m[2]) for i, m in enumerate(members)] + [('', '', 'Total', len(members))]
            print(grid(('#', 'Módulo', 'Tipo', 'Espécie'), rows, {0}))
        return

    if args.conflitos:
        pairs = collections.Counter((hits[0], hits[1]) for _, hits in overlaps)
        rows = []
        for (winner, loser), qty in pairs.most_common():
            examples = [n for n, h in overlaps if h[0] == winner and h[1] == loser][:4]
            rows.append((qty, winner, loser, ', '.join(examples)))
        rows.append((sum(pairs.values()), 'Total', '', ''))
        print(grid(('Tipos', 'Venceu', 'Também atendia', 'Exemplos'), rows, {0}))
        return

    rows = [(i + 1, cat, qty, f'{100.0 * qty / total:.1f}%'.replace('.', ','))
            for i, (cat, qty) in enumerate(counts.most_common())]
    rows.append(('', 'Total', total, '100,0%'))
    print(grid(('#', 'Categoria', 'Tipos', '%'), rows, {0, 2, 3}))
    if counts.get('SEM CATEGORIA'):
        print('\nSem categoria:', ', '.join(sorted(r[2] for r in result if r[0] == 'SEM CATEGORIA')))


if __name__ == '__main__':
    main()
