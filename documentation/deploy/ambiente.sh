# Item D do deploy: as propriedades de producao, copiadas de C:\segredos\producao.json. Copiado para /opt/jobsnow/ambiente.sh.
# Este arquivo nao guarda segredo: o JSON fica em /opt/jobsnow/application_properties.json, legivel so pelo usuario jobsnow.
export application_properties="$(cat /opt/jobsnow/application_properties.json)"
