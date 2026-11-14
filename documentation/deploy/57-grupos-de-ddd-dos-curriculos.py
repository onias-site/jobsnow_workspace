# Carga dos grupos de ddd dos curriculos (2026-11-12): le os vis_resume ja gravados (ativos -> jn_grouper) e os
# vis_inactive_resume (inativos -> jn_inactive_grouper) e grava, para cada ddd, o grupo de VisEntityVirtualDddGrouper
# cujo child e a lista de textos JSON de cada curriculo com aquele ddd: btc, clt, disponibility, experience,
# spokenLanguage (a lista inteira, cada item como esta gravado), pcd, pj, resumeType, temporallyJobTime, travel e o id
# do curriculo (o _id do documento). E o que o decorator de @CcpEntityGrouperChild(childFields = ...) mantem a cada
# escrita do curriculo depois do deploy da vis e dos consumidores; os curriculos ja gravados so entram por esta carga.
# Idempotente: recalcula cada grupo do zero e o sobrescreve; um ddd sem curriculo tem o grupo apagado (so os grupos
# de vis_virtual_ddd_grouper sao tocados). Rodar logo depois do deploy: um curriculo salvo durante a carga pode ficar
# com a versao lida pela carga ate a proxima gravacao dele.
# Ids calculados pelo framework (VisEntityVirtualDddGrouper.calculateId e JnEntityGrouper.calculateId, iguais nos dois
# lados do grouper), um par por ddd permitido em VisJsonCommonsFields.ddd.
# Uso: powershell -File com-tunel-de-producao.ps1 -Script 57-grupos-de-ddd-dos-curriculos.py
#      ou: ES_DESTINO_AUTH=<valor> python 57-grupos-de-ddd-dos-curriculos.py [destino]
# Imprime so contagens; nao imprime e-mails nem dados dos candidatos.
import json
import os
import sys
import urllib.error
import urllib.request

PARENT_NAME = "vis_virtual_ddd_grouper"
CHILD_NAME = "vis_resume"
CHILD_FIELDS = ["btc", "clt", "disponibility", "experience", "spokenLanguage", "pcd", "pj", "resumeType",
                "temporallyJobTime", "travel"]
SIDES = [("vis_resume", "jn_grouper"), ("vis_inactive_resume", "jn_inactive_grouper")]

# ddd: (parentId, id do documento no jn_grouper e no jn_inactive_grouper)
GROUPS = {
    10: ("-4e2a87eeee27b084c01ba5f7ad1a68a73285781b", "-3dc33649314b530a3e2f933b23763ade46c09b55"),
    61: ("6c1e671f9af5b46d9c1a52067bdf0e53685674f7", "-2406af9a65301503b78c7990c034059293afa8f9"),
    62: ("511a418e72591eb7e33f703f04c3fa16df6c90bd", "3a2add2d7885033128c8971673bc24a543b6e4bb"),
    64: ("-39939ae8a0133cefc4c4a784164a4dcf776379d8", "62b0275e34eef5d4462a206c7f5d89a601fe48fd"),
    65: ("2a459380709e2fe4ac2dae5733c73225ff6cfee1", "3a8e1535a8fa791a6eafe40d4d5853bc717a2f1a"),
    66: ("59129aacfb6cebbe2c52f30ef3424209f7252e82", "44d245b47b09ef66fa6fe254610f3be075020b07"),
    67: ("4d89d294cd4ca9f2ca57dc24a53ffb3ef5303122", "-7a83ca85eb6ca27601f0ad728f7daf70476ca6fa"),
    82: ("76546f9a641ede2beab506b96df1688d889e629a", "2bc7965423bd943c004905ba2673d1d026043d83"),
    71: ("-2fda9f2262824bb989d88ba4298fe17f6003591d", "6ba68e2e088e015e4464cdfac5d11633fe4a8700"),
    73: ("35e995c107a71caeb833bb3b79f9f54781b33fa1", "26da4d4e814dbcab554f6ed35cc6e19bad5f5343"),
    74: ("1f1362ea41d1bc65be321c0a378a20159f9a26d0", "-593fb3d5ebd62d89e24c1617056916a83b19ec4e"),
    75: ("450ddec8dd206c2e2ab1aeeaa90e85e51753b8b7", "-72c738799d2253bf9d645b05c70fe642b0ee4b47"),
    77: ("-2cde2908330674aeabf13626cc0df76750c428e2", "-71dbef2668833eadc2e187554cd82e2d5421843c"),
    85: ("1352246e33277e9d3c9090a434fa72cfa6536ae2", "136f31dfa8f204310f5ea0e17dd0082f6cd2c79d"),
    88: ("-4c80922310528179a87c82ce880610db9d067531", "-61bfc34e18a14d6bf17bb8b776682999c304b3c3"),
    98: ("31bd9b9f5f7b338e41b56183a2f3008b541d7c84", "-61bc7cc1241522b2eb1ff462ae63fd16189d6dcd"),
    99: ("-6586419ee1fd981e26bc25f8c8393ae419879a60", "-44c84729cc3339e0a071e8766dabc9fdbdb64bc0"),
    83: ("7d7116e23efef7292cad5e6f033d9a962708228c", "706fe64c2a3a4fb0e65f63f9a017420961b598bb"),
    81: ("1d513c0bcbe33b2e7440e5e14d0b22ef95c9d673", "-69bffb67f7a235f481245af39f5bfd61ee57214d"),
    87: ("-19d280e14bc2783dfd2d0e9b459ed6818e417f0c", "-65912cfdf0ec75a7cf3f5dce8df38a12c45aed66"),
    86: ("3c26dffc8a2e8804dfe2c8a1195cfaa5ef6d0014", "-553fb424e784ed9b8e1d4058c48f9d2729a2dc91"),
    89: ("16b06bd9b738835e2d134fe8d596e9ab0086a985", "2a23c9ba485a1baf97da39db33e6a9c268e34fa"),
    84: ("-41b9e5f32e025fad5963c026b0730a09079505cc", "424b2e806450965d171dd342f25dcddc85a48d5c"),
    79: ("-48b0a116b9eb6a45a35b38d58ef75dc6fb3d85fb", "-719a72eeb034724203bf1c1e5adb7283faeed518"),
    68: ("-4b36927f7ab22d8189273361de69f11425ad169e", "3c274e85bbc729c81cee5a32d4bdb5b682a1b94"),
    96: ("6fb84aed32facd1299ee1e77c8fd2b1a6352669e", "-4c0b2a2463544811bbfe44dc1597429ab56dd283"),
    92: ("-711ae3555d3d0b11d1a4b4810a57624820ef9729", "-280a82cc7c405bdb9dd7c8029ebd83695509cfbc"),
    97: ("-7ed12ba9d2cdeec9c5847ec55632d30fbd49c44e", "-f81d28a2b71df6d463ee92ae5a89882531418e1"),
    91: ("4cd66dfabbd964f8c6c4414b07cdb45dae692e19", "58f29ed06d86f5d05f265cf59e3ff8c3b46bdb19"),
    93: ("8a35293e09f508494096c1c1b3819edb9df50db", "2f752513e149cceca4c8fc39ac4e5e2bfab8fcdf"),
    94: ("215bb47da8fac3342b858ac3db09b033c6c46e0b", "56bed4a87afa8e4809ec902bdc98318fc72da506"),
    69: ("-58d4dff9d13d3b854d3146853e4117e707493935", "5b5c463540383a464b83236c6b00199dcefcfca6"),
    95: ("-719c02c1888694efda764e45e1bbbe3867d1bece", "6b169ed4d185be4ac960ce955f1dd145ee00b1c4"),
    63: ("-5e8aab5f2d4ea599b3f18c6ffe7babb0e618fdd9", "-263f98501e0ff56795e9e6e2257361e39508bd83"),
    27: ("-43cc15b1d91a1e50ebf7cdebe96a9eec5b9a789d", "5c4ea6e6f286f64fc38c2ff90170ac7444ccf3c"),
    28: ("a57cb53ba59c46fc4b692527a38a87c78d84028", "-2cb124ff2424471410ec1b47cb8cb536218560ec"),
    31: ("632667547e7cd3e0466547863e1207a8c0c0c549", "-342cb38280d45828cb992defc383e2f13b6a6f35"),
    32: ("-34b1adf74b3278d974df71b6bad1291765971f48", "181188395ae197790bbc27b198bcd50399eae944"),
    33: ("-4996d15a206df35296e3dfce659000285b589948", "-1693c3dd2cbf53b24e1f441f1b7c16779465fec4"),
    34: ("-e07c934b159104d5f4e4660be5274efc100b4a7", "-6c5d60f3b5e523bbd210b7df0efdc342aab5024e"),
    35: ("-68d5983b7e6d8d75cb686265cae9b3ed6abfe48f", "-38424f47db1be98b5dad8e31ce8503b2400c6e82"),
    37: ("-3485e288a17ff02e11bfb60823561fbe14645f7d", "599317d2e5870f97ed452cb2adc51ee10d0b2a47"),
    38: ("5b384ce32d8cdef02bc3a139d4cac0a22bb029e8", "10009969da5b56972aec178065623548d5317e8f"),
    21: ("472b07b9fcf2c2451e8781e944bf5f77cd8457c8", "7800a7b7fcfec6baca57a82609e5336de227e93b"),
    22: ("12c6fc06c99a462375eeb3f43dfd832b08ca9e17", "-6a0da3a3780e9d366549d03f8a44d1394338ccda"),
    24: ("4d134bc072212ace2df385dae143139da74ec0ef", "4a3d80ab1ccbebb1a732b82cb65e991fbbc51f0c"),
    11: ("17ba0791499db908433b80f37c5fbc89b870084b", "-3fa8d0ff1f9f038914baef49ef8b578bea691aff"),
    12: ("7b52009b64fd0a2a49e6d8a939753077792b0554", "5d79e2b90485e0aac44463e6c46a88916b8810bf"),
    13: ("-42cf85c13cd61ef5d30070478b7f7dc25eeb070c", "4a19c5f5f79c4c3b1fba37bb1524fa5fd40f2907"),
    14: ("-5ca1e6dede1540c254060a1595424343ef853c5", "da4a77a46673c3802d0d5dee680f5efa0d2b93f"),
    15: ("-e54298fca71fc93ced691994c4993c7d53ff7ee", "-8dc8d798dad1cb945289b93ad946aed9a683db8"),
    16: ("1574bddb75c78a6fd2251d61e2993b5146201319", "28fae0664d30abed37e84596884e1e35eafb5af0"),
    17: ("716d9708d321ffb6a00818614779e779925365c", "-7eff26dfd9fb39f481141152faa9e0db79701019"),
    18: ("-6195aa494ba9c19ad5dc41629dc35afaa3ca96c0", "29e9db487325e92d5cdedb838b52a85598ad536"),
    19: ("-4c0f38094489c50e416e2618b154014e6623e0e1", "486de3dda6aaabb484d2078411a6e30e204a89ec"),
    41: ("761f22b2c1593d0bb87e0b606f990ba4974706de", "4d3b5e25124fec3e0759f0554453fc89ce602518"),
    42: ("-6d30314c62a826eb1274eb2f1c89bc21f86851aa", "695597b85af1cbc0bc67feac82218cd958fbd344"),
    43: ("286dd552c9bea9a69ecb3759e7b94777635514b", "18c084f2524b0889e0c6c98619f8d4496ebe0fe4"),
    44: ("-67043bd05123fdb6dc6834a69d15c5c003f56dbd", "200cbfaf07470f5cecb65ff94cfe2279b697fad1"),
    45: ("-49bbcaea9f27d6901925ccddc94e0729e4d7d76", "-7dc266f8a1e411bd224e1fd8f1c69607729886f"),
    46: ("-1d10b6a5eeada9ea8d6b687b3e940dc544d7fa9", "458dfa4b10f68a6d2d0aa5826540cb23c79f21dd"),
    51: ("-4814939763fc8de8f86899024883c453c1ae34b4", "-7a20ea541e6fba2ce2b677160104c76d56196b42"),
    53: ("-3a48925c19f72cb124f8dbb326478a11796f9cd8", "2d70d1dce76b7112faab24356aebceffa39297ba"),
    54: ("-7f1d75ae343d905b42cb6c73a1a6c4c9eb90a1f4", "2195a0254b4495c96b6c2a8befe9721ad7470925"),
    55: ("-710011bf639da1e5d270afcc9ce7bf1931e2349c", "326e6bc2377df8c28c191da62ba57e5fae501540"),
    47: ("-7d8403ba78f70f4bbdff636367c9081b49aaa805", "472ba67badf693ccc7e0378502cf1192045bfef4"),
    48: ("64e095fe763fc62418378753f9402623bea9e227", "-51dcd942e36a14e641c5c8306f2c1b0402263aeb"),
    49: ("2e01e17467891f7c933dbaa00e1459d23db3fe4f", "-eae1244d8ee6b39294ead212b3477c61147fdce"),
}

target_url = sys.argv[1].rstrip("/") if len(sys.argv) > 1 else "http://127.0.0.1:9210"
auth = os.environ.get("ES_DESTINO_AUTH", "")
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def skills_from_resume(source):
    # childFieldsProducers = VisResumeSkillsFromResumeChildField: skill.filter(x -> x.type == 'skillsFromResume').map(x -> x.skill)
    return [item.get("skill") for item in (source.get("skill") or []) if isinstance(item, dict) and item.get("type") == "skillsFromResume"]


def call(method, path, body=None):
    data = None if body is None else json.dumps(body).encode("utf-8")
    request = urllib.request.Request(target_url + path, data=data, method=method)
    request.add_header("Content-Type", "application/json")
    if auth:
        request.add_header("Authorization", auth)
    try:
        with opener.open(request) as response:
            return response.status, json.loads(response.read() or b"{}")
    except urllib.error.HTTPError as error:
        return error.code, json.loads(error.read() or b"{}")


def resumes(index):
    status, page = call("POST", "/" + index + "/_search?scroll=2m", {"size": 500, "_source": ["ddd"] + CHILD_FIELDS + ["skill"]})
    if status == 404:
        return
    if status != 200:
        print("falha ao ler", index, status, page)
        sys.exit(1)
    while page["hits"]["hits"]:
        for hit in page["hits"]["hits"]:
            yield hit["_id"], hit["_source"]
        status, page = call("POST", "/_search/scroll", {"scroll": "2m", "scroll_id": page["_scroll_id"]})
    call("DELETE", "/_search/scroll", {"scroll_id": page["_scroll_id"]})


def to_ddd(value):
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


failures = 0
print("lado\tcurriculos\tsem ddd valido\tddds com grupo\tgrupos apagados\tchildren gravados\tconferidos")
for resume_index, grouper_index in SIDES:
    children_by_ddd = {ddd: [] for ddd in GROUPS}
    total = 0
    without_ddd = 0
    for resume_id, source in resumes(resume_index):
        total += 1
        child = {field: source[field] for field in CHILD_FIELDS if field in source and source[field] is not None}
        child["skill"] = skills_from_resume(source)
        child["id"] = resume_id
        child_text = json.dumps(child, ensure_ascii=False, separators=(",", ":"))
        ddds = []
        for value in source.get("ddd") or []:
            ddd = to_ddd(value)
            if ddd in GROUPS and ddd not in ddds:
                ddds.append(ddd)
        if not ddds:
            without_ddd += 1
        for ddd in ddds:
            children_by_ddd[ddd].append(child_text)

    written = 0
    deleted = 0
    children_count = 0
    checked = 0
    for ddd, children in children_by_ddd.items():
        parent_id, group_id = GROUPS[ddd]
        path = "/" + grouper_index + "/_doc/" + group_id
        if not children:
            status, _ = call("DELETE", path)
            if status == 200:
                deleted += 1
            elif status != 404:
                failures += 1
                print("falha ao apagar o grupo do ddd", ddd, "em", grouper_index, status)
            continue
        group = {
            "parentId": parent_id,
            "parentName": PARENT_NAME,
            "childName": CHILD_NAME,
            "parentJson": {"ddd": ddd},
            "child": children,
            "childCount": len(children),
        }
        status, answer = call("PUT", path, group)
        if status not in (200, 201):
            failures += 1
            print("falha ao gravar o grupo do ddd", ddd, "em", grouper_index, status, answer)
            continue
        written += 1
        children_count += len(children)
    call("POST", "/" + grouper_index + "/_refresh")
    for ddd, children in children_by_ddd.items():
        if not children:
            continue
        status, stored = call("GET", "/" + grouper_index + "/_doc/" + GROUPS[ddd][1])
        if status == 200 and stored.get("_source", {}).get("child") == children:
            checked += 1
        else:
            failures += 1
            print("grupo do ddd", ddd, "em", grouper_index, "nao confere:", status)
    print(f"{grouper_index}\t{total}\t{without_ddd}\t{written}\t{deleted}\t{children_count}\t{checked}")

print("OK" if failures == 0 else f"FALHAS: {failures}")
sys.exit(0 if failures == 0 else 1)
