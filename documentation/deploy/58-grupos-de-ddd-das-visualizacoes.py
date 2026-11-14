# Carga dos grupos de ddd das visualizacoes de curriculo (2026-11-12): para cada vis_viewed_resume ja gravado, acha o
# curriculo visualizado (o vis_resume, ou o vis_inactive_resume, cujo linkedinAddress tem o SHA-1 igual ao linkedin da
# visualizacao), grava na visualizacao o campo ddd (os ddds do curriculo) e poe a visualizacao no grupo de cada ddd de
# VisEntityVirtualViewedResumeDddGrouper (parentName vis_virtual_viewed_resume_ddd_grouper, so no jn_grouper: a
# visualizacao nao tem gemea). O child e o texto JSON com btc, clt, disponibility, experience, spokenLanguage (a lista
# inteira, cada item como esta gravado), pcd, pj, resumeType, temporallyJobTime, travel do curriculo e o id da
# visualizacao (o _id do documento). E o que o decorator de @CcpEntityGrouperChild(childFields = ...) do
# VisEntityViewedResume mantem a cada visualizacao depois do deploy da vis; as ja gravadas so entram por esta carga.
# Diferenca inevitavel: a carga usa o curriculo como ele esta hoje, nao como estava no dia da visualizacao.
# Passo 1: acrescenta ddd (integer) ao mapeamento de vis_viewed_resume (idempotente; igual ao local).
# Passo 2: idempotente; recalcula cada grupo do zero e o sobrescreve, um ddd sem visualizacao tem o grupo apagado (so os
# grupos de vis_virtual_viewed_resume_ddd_grouper sao tocados).
# Rodar logo depois do deploy da vis. A visualizacao fica 1 hora no cache: salva de novo nessa hora com outros ddds, ela
# pode ficar tambem no grupo do ddd antigo ate a proxima gravacao.
# Ids calculados pelo framework, um par por ddd permitido em VisJsonCommonsFields.ddd.
# Uso: powershell -File com-tunel-de-producao.ps1 -Script 58-grupos-de-ddd-das-visualizacoes.py
#      ou: ES_DESTINO_AUTH=<valor> python 58-grupos-de-ddd-das-visualizacoes.py [destino]
# Imprime so contagens; nao imprime e-mails, LinkedIn nem dados dos candidatos.
import hashlib
import json
import os
import sys
import urllib.error
import urllib.request

PARENT_NAME = "vis_virtual_viewed_resume_ddd_grouper"
CHILD_NAME = "vis_viewed_resume"
CHILD_FIELDS = ["btc", "clt", "disponibility", "experience", "spokenLanguage", "pcd", "pj", "resumeType",
                "temporallyJobTime", "travel"]
RESUME_INDICES = ["vis_resume", "vis_inactive_resume"]

# ddd: (parentId, id do documento no jn_grouper)
GROUPS = {
    10: ("-4e2a87eeee27b084c01ba5f7ad1a68a73285781b", "6e9c2f335dcd523d16791b8af2e996df2dcc52"),
    61: ("6c1e671f9af5b46d9c1a52067bdf0e53685674f7", "6d1548c89757793c0751e7fc27e1652205d8f5a8"),
    62: ("511a418e72591eb7e33f703f04c3fa16df6c90bd", "467ac717902584ee908a426407bcae64792b4fbc"),
    64: ("-39939ae8a0133cefc4c4a784164a4dcf776379d8", "-14ae2fe8c38d66667a31ed64e55e2b51f294e970"),
    65: ("2a459380709e2fe4ac2dae5733c73225ff6cfee1", "1fd7054b65be6fa932f4fce034eee7ded74a851"),
    66: ("59129aacfb6cebbe2c52f30ef3424209f7252e82", "611b8a5f7c8e1ea1d2b74f33631687f3fdc2867f"),
    67: ("4d89d294cd4ca9f2ca57dc24a53ffb3ef5303122", "69643e3edda53417029ff194517bc2480cf98376"),
    82: ("76546f9a641ede2beab506b96df1688d889e629a", "-3fc2ade9125b4cdebcf7728e8bb2aa4ebf76b793"),
    71: ("-2fda9f2262824bb989d88ba4298fe17f6003591d", "7fbfd1204f73dbbd41ec3280bb805b4c4683b40d"),
    73: ("35e995c107a71caeb833bb3b79f9f54781b33fa1", "-5283b6da5d12c9c1e44418eeb324d7cd0f29af7b"),
    74: ("1f1362ea41d1bc65be321c0a378a20159f9a26d0", "-352c5c22e1ad07db72a975c90f7eb7ab41640673"),
    75: ("450ddec8dd206c2e2ab1aeeaa90e85e51753b8b7", "-35e3777a4f5c51a286d221376ad25d21cc1aad19"),
    77: ("-2cde2908330674aeabf13626cc0df76750c428e2", "6577b4872c50d008cd0acb8fd45941ab6935a4b"),
    85: ("1352246e33277e9d3c9090a434fa72cfa6536ae2", "-5f341980baee7cf1c878109ff8e9f8218e8643f0"),
    88: ("-4c80922310528179a87c82ce880610db9d067531", "-2b3a3c704f94403d561d7243c95982eb6550cbee"),
    98: ("31bd9b9f5f7b338e41b56183a2f3008b541d7c84", "-4e51ff0a38b3dded285e5aefd9b7047e0ef03e96"),
    99: ("-6586419ee1fd981e26bc25f8c8393ae419879a60", "15d4c4d771e317b53bfb859cc2a800d5bee19ce2"),
    83: ("7d7116e23efef7292cad5e6f033d9a962708228c", "3f90e701f75735b3ea5cc80c435496cac27f602f"),
    81: ("1d513c0bcbe33b2e7440e5e14d0b22ef95c9d673", "85dc1bf607317d0744b1807dbece7798bfb9317"),
    87: ("-19d280e14bc2783dfd2d0e9b459ed6818e417f0c", "572b92d29769b4593eb5bde2df8bf78dd18740d6"),
    86: ("3c26dffc8a2e8804dfe2c8a1195cfaa5ef6d0014", "-2882125ad304af979814ae0150e288b608aad503"),
    89: ("16b06bd9b738835e2d134fe8d596e9ab0086a985", "-597315408a515f42e418f855d9c6384c98f27133"),
    84: ("-41b9e5f32e025fad5963c026b0730a09079505cc", "-6e4f25fc1b0f7c3ba8eb2563b7aafb9808178b"),
    79: ("-48b0a116b9eb6a45a35b38d58ef75dc6fb3d85fb", "3f7335181afd30e85d746650ac466b0e959819e6"),
    68: ("-4b36927f7ab22d8189273361de69f11425ad169e", "2135b8b7fcea21cb3e196775ed49256b736e6c6a"),
    96: ("6fb84aed32facd1299ee1e77c8fd2b1a6352669e", "-2f9f370143762f50cca210ebfdf2fc5c2ff3e93"),
    92: ("-711ae3555d3d0b11d1a4b4810a57624820ef9729", "5100f059fa018cf01c0eb45503d803329eef46fb"),
    97: ("-7ed12ba9d2cdeec9c5847ec55632d30fbd49c44e", "521c241eaba65fbb8eb43d0272a1709d69aa5269"),
    91: ("4cd66dfabbd964f8c6c4414b07cdb45dae692e19", "3deebe4c29b00915d612b6aff0a3f268301ee166"),
    93: ("8a35293e09f508494096c1c1b3819edb9df50db", "3ec149f284163fbc72d568162460b378c242089d"),
    94: ("215bb47da8fac3342b858ac3db09b033c6c46e0b", "-2eaf8341b0b3a9624ec97db5f687aaaf6f97870a"),
    69: ("-58d4dff9d13d3b854d3146853e4117e707493935", "637f712ac9c5319909317377ef5b368df67a1412"),
    95: ("-719c02c1888694efda764e45e1bbbe3867d1bece", "96e8820820475db2fb06cced3dddb707a99b24e"),
    63: ("-5e8aab5f2d4ea599b3f18c6ffe7babb0e618fdd9", "-55584c93e343e0566964a8062e1641df055c0ca1"),
    27: ("-43cc15b1d91a1e50ebf7cdebe96a9eec5b9a789d", "-6b5d2ccd2a680dc75431caa9ae44e5d3e0181b2e"),
    28: ("a57cb53ba59c46fc4b692527a38a87c78d84028", "-2aceb036bd1beb0e128a339489c1d8a4fda2324f"),
    31: ("632667547e7cd3e0466547863e1207a8c0c0c549", "-4339fd914cc2919fab93ad38fda6283ed5493c0b"),
    32: ("-34b1adf74b3278d974df71b6bad1291765971f48", "1bf0f2b1a9b7898f671d48da5e76a69835706845"),
    33: ("-4996d15a206df35296e3dfce659000285b589948", "-579fa7ae914fe3eaeebcbda4b511ccf84be4cb55"),
    34: ("-e07c934b159104d5f4e4660be5274efc100b4a7", "-27942b0e88e76ed9943f323bdea4feea36eb6c68"),
    35: ("-68d5983b7e6d8d75cb686265cae9b3ed6abfe48f", "-5a5c0afac9db930fb80e19556d579d5725b38863"),
    37: ("-3485e288a17ff02e11bfb60823561fbe14645f7d", "60d2f46e02f1ed77da0ee5aeaaa45e07c323fa45"),
    38: ("5b384ce32d8cdef02bc3a139d4cac0a22bb029e8", "19b3cf67c67657136a83476481883eb5349d642e"),
    21: ("472b07b9fcf2c2451e8781e944bf5f77cd8457c8", "5002bb60cce345ecd908f5a49bfd679b1a4108a8"),
    22: ("12c6fc06c99a462375eeb3f43dfd832b08ca9e17", "7a2bad81d818e9e813fcc4a00b49d7852654b304"),
    24: ("4d134bc072212ace2df385dae143139da74ec0ef", "-718b93502cf41e48ed64cdb95e31388e5c81ddd7"),
    11: ("17ba0791499db908433b80f37c5fbc89b870084b", "-6c9c504cc1d1fbf45fb1e2436f553ac77947c05a"),
    12: ("7b52009b64fd0a2a49e6d8a939753077792b0554", "-4fca73a5bb48695b65cf091cfc1f2228c468b91a"),
    13: ("-42cf85c13cd61ef5d30070478b7f7dc25eeb070c", "-6041bc7157cebb0dd3cdcbf607a385b3ecbdad74"),
    14: ("-5ca1e6dede1540c254060a1595424343ef853c5", "-7d6ebee013ef83ce4ed139b49d0b33f376aef1eb"),
    15: ("-e54298fca71fc93ced691994c4993c7d53ff7ee", "-5120c2c5b93a06ae8dce21396812a69c935b5758"),
    16: ("1574bddb75c78a6fd2251d61e2993b5146201319", "725148d43eb0997d9d95d4b40c51d8e88ae20f39"),
    17: ("716d9708d321ffb6a00818614779e779925365c", "1a431b6f3cbf6cbb3c1e8575f621b1f459772f7f"),
    18: ("-6195aa494ba9c19ad5dc41629dc35afaa3ca96c0", "7d658f7498b7014b7adf7865829f91b7aa4b7cc3"),
    19: ("-4c0f38094489c50e416e2618b154014e6623e0e1", "46425025e98ad2c274baf5518533ea0f18838834"),
    41: ("761f22b2c1593d0bb87e0b606f990ba4974706de", "71f2aac161dbbe98b73b87e9d532da8ffd8c3d5a"),
    42: ("-6d30314c62a826eb1274eb2f1c89bc21f86851aa", "47c4697136db877c3bb42853e9b9e11c8ef61e8d"),
    43: ("286dd552c9bea9a69ecb3759e7b94777635514b", "-5e759445671265924031c7d0a4f32a3c20bf0554"),
    44: ("-67043bd05123fdb6dc6834a69d15c5c003f56dbd", "-3aa2be652e519dbe67b2048f9e95308b3891aad4"),
    45: ("-49bbcaea9f27d6901925ccddc94e0729e4d7d76", "eab7a09ee0125d1f3d2069b34ed0cb233262fc0"),
    46: ("-1d10b6a5eeada9ea8d6b687b3e940dc544d7fa9", "59fe63f32bae290f1695be9dd5b4f10c7a388022"),
    51: ("-4814939763fc8de8f86899024883c453c1ae34b4", "445601dffab42007330e2f7c0692c23ebe5c5e9c"),
    53: ("-3a48925c19f72cb124f8dbb326478a11796f9cd8", "-739e054e2f2a769c1530cad889a75f4bb2bc53e1"),
    54: ("-7f1d75ae343d905b42cb6c73a1a6c4c9eb90a1f4", "6ea9ccd3c77ef3f610f1dc1db4b6753b26fda9cf"),
    55: ("-710011bf639da1e5d270afcc9ce7bf1931e2349c", "-4ea73735ff3db60fd7d0c43feb1da31c8dfbb868"),
    47: ("-7d8403ba78f70f4bbdff636367c9081b49aaa805", "-28f2dca5c3c65d517f71b9f2628d0ce99f7133e5"),
    48: ("64e095fe763fc62418378753f9402623bea9e227", "2f27d8086f475073194d78c318e284346f5ba9a5"),
    49: ("2e01e17467891f7c933dbaa00e1459d23db3fe4f", "-1f914b5e2fef0f083a807719bc244ce842b726cc"),
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


def scroll(index, fields):
    status, page = call("POST", "/" + index + "/_search?scroll=2m", {"size": 500, "_source": fields})
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


def ccp_sha1(text):
    # o SHA-1 como o framework o escreve (CcpHashDecorator.asString): BigInteger com sinal, em hexadecimal, sem os
    # zeros a esquerda; o hexdigest comum nao bate com o linkedin gravado na visualizacao
    digest = hashlib.sha1(text.encode("utf-8")).digest()
    return format(int.from_bytes(digest, "big", signed=True), "x")


def to_ddd(value):
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


failures = 0

# passo 1: o campo ddd no mapeamento
status, answer = call("PUT", "/vis_viewed_resume/_mapping", {"properties": {"ddd": {"type": "integer"}}})
if status != 200:
    print("falha ao acrescentar ddd ao mapeamento de vis_viewed_resume:", status, answer)
    sys.exit(1)
print("mapeamento de vis_viewed_resume com ddd: ok")

# os curriculos por SHA-1 do LinkedIn, os ativos antes dos inativos
resumes_by_linkedin = {}
shared_linkedin = 0
for index in RESUME_INDICES:
    for _, source in scroll(index, ["linkedinAddress", "ddd"] + CHILD_FIELDS + ["skill"]):
        address = source.get("linkedinAddress")
        if not address:
            continue
        linkedin_hash = ccp_sha1(address)
        if linkedin_hash in resumes_by_linkedin:
            shared_linkedin += 1
            continue
        resumes_by_linkedin[linkedin_hash] = source

children_by_ddd = {ddd: [] for ddd in GROUPS}
views = 0
without_resume = 0
updated_views = 0
for view_id, view in scroll("vis_viewed_resume", ["linkedin"]):
    views += 1
    resume = resumes_by_linkedin.get(view.get("linkedin"))
    if resume is None:
        without_resume += 1
        continue
    ddds = []
    for value in resume.get("ddd") or []:
        ddd = to_ddd(value)
        if ddd in GROUPS and ddd not in ddds:
            ddds.append(ddd)
    status, answer = call("POST", "/vis_viewed_resume/_update/" + view_id, {"doc": {"ddd": ddds}})
    if status != 200:
        failures += 1
        print("falha ao gravar ddd numa visualizacao:", status, answer.get("error", {}).get("type"))
        continue
    updated_views += 1
    child = {field: resume[field] for field in CHILD_FIELDS if field in resume and resume[field] is not None}
    child["skill"] = skills_from_resume(resume)
    child["id"] = view_id
    child_text = json.dumps(child, ensure_ascii=False, separators=(",", ":"))
    for ddd in ddds:
        children_by_ddd[ddd].append(child_text)
call("POST", "/vis_viewed_resume/_refresh")

written = 0
deleted = 0
children_count = 0
for ddd, children in children_by_ddd.items():
    parent_id, group_id = GROUPS[ddd]
    path = "/jn_grouper/_doc/" + group_id
    if not children:
        status, _ = call("DELETE", path)
        if status == 200:
            deleted += 1
        elif status != 404:
            failures += 1
            print("falha ao apagar o grupo do ddd", ddd, status)
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
        print("falha ao gravar o grupo do ddd", ddd, status, answer)
        continue
    written += 1
    children_count += len(children)
call("POST", "/jn_grouper/_refresh")

checked = 0
for ddd, children in children_by_ddd.items():
    if not children:
        continue
    status, stored = call("GET", "/jn_grouper/_doc/" + GROUPS[ddd][1])
    if status == 200 and stored.get("_source", {}).get("child") == children:
        checked += 1
    else:
        failures += 1
        print("grupo do ddd", ddd, "nao confere:", status)

print("visualizacoes\tsem curriculo\tcom ddd gravado\tLinkedIn repetido\tgrupos gravados\tgrupos apagados\tchildren\tconferidos")
print(f"{views}\t{without_resume}\t{updated_views}\t{shared_linkedin}\t{written}\t{deleted}\t{children_count}\t{checked}")
print("OK" if failures == 0 else f"FALHAS: {failures}")
sys.exit(0 if failures == 0 else 1)
