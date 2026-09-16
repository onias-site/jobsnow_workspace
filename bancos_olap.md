# Bancos de Dados OLAP — Lista Completa

## Colunares Open-Source

| Banco | Detalhe |
|---|---|
| **ClickHouse** | Mais rápido para analytics em tempo real |
| **Apache Druid** | Otimizado para séries temporais e dashboards |
| **Apache Pinot** | Criado no LinkedIn, foco em baixíssima latência |
| **DuckDB** | OLAP embarcado (roda no processo, sem servidor) |
| **Apache Parquet** | Formato colunar (não é banco, mas base de muitos) |
| **MonetDB** | Pioneiro colunar, acadêmico/pesquisa |
| **VectorWise** | Derivado do MonetDB |
| **StarRocks** | Fork do Apache Doris, muito performático |
| **Apache Doris** | Colunar com SQL completo |

## Colunares Cloud (managed)

| Banco | Provedor |
|---|---|
| **BigQuery** | Google Cloud |
| **Redshift** | AWS |
| **Snowflake** | Multi-cloud (AWS/GCP/Azure) |
| **Synapse Analytics** | Azure |
| **Databricks SQL** | Multi-cloud |
| **Firebolt** | Cloud independente |
| **Rockset** | Real-time analytics cloud |

## MPP (Massively Parallel Processing)

Distribuem queries em centenas de nós simultâneos:

| Banco | Detalhe |
|---|---|
| **Greenplum** | Fork do PostgreSQL para analytics |
| **Teradata** | Enterprise clássico, décadas no mercado |
| **Netezza** | IBM, hardware+software integrado |
| **Vertica** | HP/Micro Focus, colunar MPP |
| **Exasol** | Alto desempenho em memória |
| **Yellowbrick** | MPP moderno com hardware dedicado |

## HTAP (Híbrido OLTP + OLAP)

Tentam resolver os dois ao mesmo tempo:

| Banco | Detalhe |
|---|---|
| **TiDB** | MySQL-compatível, HTAP distribuído |
| **SingleStore (MemSQL)** | In-memory, rowstore + columnstore |
| **CockroachDB** | Foco OLTP mas com capacidades analíticas |
| **YugabyteDB** | PostgreSQL-compatível, HTAP |
| **OceanBase** | Alibaba, muito usado na China |

## Timeseries com capacidades OLAP

| Banco | Detalhe |
|---|---|
| **TimescaleDB** | Extensão PostgreSQL para séries temporais |
| **InfluxDB** | Métricas e monitoramento |
| **QuestDB** | Colunar + timeseries, muito rápido |
| **kdb+** | Financeiro, décadas no mercado |
| **TDengine** | IoT e séries temporais |

## Relacionais tradicionais com modo OLAP

| Banco | Detalhe |
|---|---|
| **PostgreSQL + cstore_fdw** | Extensão colunar |
| **SQL Server** | Columnstore Index nativo desde 2012 |
| **Oracle** | In-Memory Column Store desde 12c |
| **MySQL** | HeatWave (extensão OLAP da Oracle) |

## Motores de Query sobre Data Lakes

Não são bancos em si, mas fazem OLAP sobre arquivos:

| Ferramenta | Detalhe |
|---|---|
| **Apache Hive** | SQL sobre Hadoop/HDFS |
| **Apache Spark SQL** | Analytics distribuído em memória |
| **Presto / Trino** | Query federada sobre múltiplas fontes |
| **Apache Impala** | Cloudera, SQL sobre HDFS |
| **Dremio** | Query sobre data lake com aceleração |
| **Starburst** | Trino gerenciado |

## Cubos OLAP (modelo multidimensional clássico)

Conceito mais antigo — pré-agrega dados em "cubos":

| Ferramenta | Detalhe |
|---|---|
| **Microsoft SSAS** | SQL Server Analysis Services |
| **Apache Kylin** | Cubos sobre Hadoop |
| **Mondrian** | Open-source, base do Pentaho |
| **Oracle OLAP** | Embutido no Oracle DB |

## Mapa mental resumido

```
OLAP
├── Colunar puro        → ClickHouse, DuckDB, BigQuery, Snowflake
├── MPP enterprise      → Teradata, Vertica, Greenplum
├── Timeseries          → QuestDB, TimescaleDB, InfluxDB
├── HTAP                → TiDB, SingleStore
├── Data lake query     → Trino, Spark SQL, Dremio
└── Cubos clássicos     → SSAS, Kylin
```

O mercado caminha para consolidar nas opções **cloud colunares** (Snowflake, BigQuery, Redshift)
e **open-source em tempo real** (ClickHouse, Apache Pinot, Druid).

---

# Todo OLAP é Colunar?

Não. Colunar é apenas uma das formas de implementar OLAP.

## As formas de armazenamento em bancos OLAP

### 1. Colunar (a mais comum hoje)
Armazena dados por coluna. É o modelo dominante moderno.

ClickHouse, BigQuery, Snowflake, Redshift, Vertica, DuckDB.

### 2. Cubos OLAP (multidimensional — MOLAP)
Pré-agrega os dados em estruturas multidimensionais chamadas **cubos**. Não é colunar nem relacional — é um modelo próprio.

```
         Tempo
        /     \
   Região     Produto
        \     /
         Vendas
```

Microsoft SSAS, Oracle OLAP, Apache Kylin, Mondrian.

- Vantagem: queries de agregação são instantâneas (já estão calculadas)
- Desvantagem: inflexível, precisa pré-definir as dimensões

### 3. Relacional com otimizações OLAP (ROLAP)
Armazena em linhas normais mas usa índices, particionamento e paralelismo para suportar analytics.

SQL Server com Columnstore Index opcional, Oracle com In-Memory, PostgreSQL com extensões.

### 4. In-memory row-based
Armazena linhas na RAM em vez de disco. Rápido para analytics por outro motivo — latência de memória vs disco.

SAP HANA, VoltDB, SingleStore.

### 5. Híbrido linha+coluna
Mantém os dois formatos simultaneamente — linhas para escrita rápida, colunas para leitura analítica.

SingleStore, SAP HANA, TiDB.

## Resumindo

| Modelo | Exemplos | Como é rápido |
|---|---|---|
| Colunar | ClickHouse, BigQuery | Lê só as colunas necessárias |
| Cubo (MOLAP) | SSAS, Kylin | Resultado pré-calculado |
| Relacional (ROLAP) | Oracle, SQL Server | Índices e paralelismo |
| In-memory | SAP HANA, VoltDB | RAM é muito mais rápida que disco |
| Híbrido | TiDB, SingleStore | Combina estratégias |

> Colunar virou sinônimo de OLAP moderno porque é a abordagem com melhor equilíbrio entre flexibilidade e performance — mas não é a única.

---

# Todo Colunar é OLAP?

Não. Colunar é um formato de armazenamento que pode ser usado em contextos diferentes de OLAP.

## Casos onde colunar não é OLAP

### 1. Armazenamento de arquivos / data lakes
Formatos colunares usados para guardar dados, não para fazer analytics interativo:

- **Apache Parquet** — formato de arquivo colunar, usado para armazenar dados no S3, HDFS, GCS. Não é um banco.
- **Apache ORC** — similar ao Parquet, usado no ecossistema Hadoop.
- **Apache Arrow** — formato colunar **in-memory**, usado para transferência de dados entre sistemas.

Esses formatos são a **base** sobre a qual bancos OLAP constroem, mas eles sozinhos não são OLAP.

### 2. Compressão e armazenamento eficiente
Algumas aplicações usam armazenamento colunar simplesmente para **comprimir melhor** os dados, sem objetivo analítico:

- Colunas com poucos valores distintos (ex: status, país) comprimem muito bem
- Sistemas de log e arquivamento usam isso para economizar espaço

### 3. Colunar dentro de bancos OLTP
Alguns bancos OLTP adicionaram armazenamento colunar como recurso opcional, sem virar OLAP:

- **SQL Server** — Columnstore Index pode ser adicionado a tabelas OLTP para acelerar algumas queries, mas o banco continua sendo OLTP
- **PostgreSQL** — extensões colunares para tabelas específicas
- **MySQL InnoDB** — suporte parcial a colunar

### 4. Sistemas embarcados / mobile
**SQLite** experimenta extensões colunares para casos específicos sem ser OLAP.

## A relação correta

```
Colunar ──────────────────────────────────────────────────────
         │                                                    │
    usado em OLAP                               usado fora de OLAP
  (ClickHouse, BigQuery)            (Parquet, Arrow, Columnstore em OLTP)
```

| | Colunar | OLAP |
|---|---|---|
| ClickHouse | sim | sim |
| BigQuery | sim | sim |
| Apache Parquet | sim | não |
| Apache Arrow | sim | não |
| SQL Server + Columnstore Index | sim (parcial) | não |
| Microsoft SSAS (cubos) | não | sim |
| SAP HANA in-memory | não | sim |

## Resumindo

> **Colunar** responde como os dados são **armazenados**.
> **OLAP** responde para que o sistema foi **projetado**.
>
> Todo OLAP moderno tende a ser colunar, mas nem todo colunar é OLAP.

---

# OLAP é sinônimo de DW?

Não — mas estão tão ligados que a confusão é natural.

```
OLAP:   forma de PROCESSAR dados analíticos (conceito, paradigma)
DW:     lugar onde dados analíticos são ARMAZENADOS (infraestrutura)
```

**Analogia:**
```
DW   = biblioteca (onde os livros ficam guardados e organizados)
OLAP = forma de pesquisar na biblioteca (por assunto, por autor, por época)
```

Na prática, todo DW é otimizado para OLAP e toda ferramenta OLAP séria precisa de um DW — por isso andam sempre juntos e parecem sinônimos.

| | OLAP | DW |
|---|---|---|
| O que é | Paradigma de consulta analítica | Infraestrutura de armazenamento |
| Tipo | Conceito | Sistema concreto |
| Exemplo | `GROUP BY`, agregações, drill-down | Teradata, BigQuery, Snowflake |

---

# O que é Timeseries?

Banco otimizado para dados que chegam continuamente com timestamp — onde **o tempo é o eixo principal de todas as queries**.

**Padrão dos dados:**
```
Banco comum:    dado pode ser qualquer coisa, tempo é só mais um campo
Timeseries:     todo dado tem timestamp + é imutável + chega em ordem cronológica
```

**Por que banco comum não serve bem:**
```
10 sensores enviando 1 dado/segundo = 864.000 registros/dia
Problemas no PostgreSQL comum:
  - índice do timestamp cresce indefinidamente → fica lento
  - queries "últimas 24h" custam caro sem particionamento manual
  - dados antigos ocupam espaço igual a dados novos
```

**O que um banco timeseries resolve:**
```
Ingestão rápida:     otimizado para muitos INSERTs contínuos
Partição automática: divide dados por janela de tempo automaticamente
Compressão:          dados antigos comprimidos automaticamente
Queries temporais:   funções nativas como "média dos últimos 5 minutos"
Retenção:            descarta dados mais antigos que X dias automaticamente
```

**Casos de uso típicos:**

| Área | O que monitora |
|---|---|
| DevOps / infraestrutura | CPU, memória, latência de servidores |
| IoT | Sensores de temperatura, pressão, velocidade |
| Financeiro | Preço de ações tick a tick |
| Energia | Consumo elétrico por segundo |
| Saúde | Batimento cardíaco, oxigenação |

**Teste prático para diferenciar Timeseries de OLAP:**
> "Os dados chegam continuamente, muitas vezes por segundo, e o tempo é sempre a primeira dimensão de qualquer query?"
```
10 sensores enviando 1 dado/segundo → Timeseries ✓
Relatório mensal de vendas carregado em lote  → OLAP / DW ✓
```

> **BigQuery NÃO é timeseries** — é OLAP/DW. Lida bem com datas, mas tempo é só mais um campo, não o eixo central da arquitetura.

---

# O que é Data Lakehouse?

Arquitetura que combina o melhor do Data Lake e do Data Warehouse.

**Os dois anteriores e seus problemas:**

```
Data Warehouse (Teradata, BigQuery, Redshift):
  + Dados estruturados, organizados, confiáveis
  + SQL, OLAP, analytics rápido
  - Caro para grandes volumes
  - Não aceita dados não-estruturados
  - Schema rígido

Data Lake (S3, GCS, HDFS):
  + Armazena qualquer coisa: CSV, JSON, imagens, logs
  + Barato — storage de objeto
  + Schema flexível
  - Dados brutos, desorganizados ("data swamp")
  - Analytics lento sem estrutura
```

**O problema da arquitetura dupla:**
```
Data Lake (S3) → ETL caro → Data Warehouse (Redshift)
Duas cópias do dado, custo duplo, dado nunca totalmente atualizado
```

**O que o Lakehouse faz:**
```
Uma única camada de storage barato (S3, GCS)
              +
Camada de metadados que adiciona:
    → transações ACID
    → schema enforcement
    → versionamento
    → otimização de queries
              ↓
Analytics direto no lake, sem mover dados
```

**Tecnologias que implementam:**

| Tecnologia | Quem mantém |
|---|---|
| **Delta Lake** | Databricks |
| **Apache Iceberg** | Netflix → Apache |
| **Apache Hudi** | Uber → Apache |

**Analogia:**
```
Data Lake:       galpão gigante — joga tudo lá, barato, impossível achar algo
Data Warehouse:  arquivo organizado — tudo catalogado, caro, só aceita documentos formatados
Data Lakehouse:  galpão gigante COM sistema de catalogação, regras e índices
```

**Produtos atuais:**
```
Databricks:   Delta Lake
Snowflake:    arquitetura similar (storage separado de compute)
Google:       BigLake (BigQuery + Cloud Storage)
AWS:          Lake Formation + S3 + Athena
Microsoft:    Microsoft Fabric (OneLake)
```

> O Lakehouse é a tendência atual — empresas novas não montam warehouse + lake separados, vão direto para Lakehouse.

---

# Conceitos de Hardware e Processamento

## O que é FPGA

**FPGA (Field-Programmable Gate Array)** é um chip que pode ser **reprogramado para fazer uma tarefa específica em hardware**.

```
CPU:    chip genérico → executa instrução 1, instrução 2... (sequencial)
FPGA:   chip reconfigurável → circuito dedicado faz TUDO ao mesmo tempo (paralelo real)
```

**Analogia — filtrar 1 bilhão de registros onde `idade > 30`:**
```
CPU:    Pega registro → verifica → descarta → ... 1 bilhão de vezes
FPGA:   O circuito É o filtro — dados passam pelo fio e saem filtrados
        Não há "verificar" — a lógica está gravada no silício
```

**O que significa "Field-Programmable":**
```
ASIC (chip fixo):   fabricado para UMA função, impossível mudar
CPU (genérico):     faz tudo, sem especialização
FPGA (meio-termo):  você programa o circuito → vira hardware dedicado
```

**Como o Netezza usou FPGA:**
```
Disco → dados brutos passam pelo FPGA → WHERE já aplicado → CPU recebe só o resultado
```

**Onde FPGAs aparecem hoje:**

| Uso | Quem usa |
|---|---|
| Filtro de dados | Netezza (IBM) |
| Inferência de IA | Microsoft Azure (servidores Bing) |
| Trading de alta frequência | Bancos — decisões em nanossegundos |
| Compressão de rede | Provedores de nuvem |

---

# Comparações Detalhadas

## Netezza vs Yellowbrick — mesma filosofia, gerações diferentes

Os dois compartilham a mesma ideia: **hardware dedicado para eliminar o gargalo entre dado e CPU em workloads analíticos MPP**.

| | Netezza | Yellowbrick |
|---|---|---|
| Modelo | Relacional | Relacional |
| SQL | Sim | Sim (PostgreSQL-compatible) |
| MPP | Sim | Sim |
| Hardware dedicado | Sim — appliance IBM | Sim — appliance próprio |
| Componente especial | FPGA (filtra antes da CPU) | NVMe SSDs + GPU/ASIC modernos |
| Época do design | Anos 2000 | Anos 2010–2020 |
| Lock-in | Total IBM | Híbrido (on-premise + cloud) |

**Por que o Yellowbrick é "Netezza da era moderna":**
```
2005: FPGA era o único jeito de ser mais rápido que CPU em filtragem
2020: NVMe SSDs são 10x mais rápidos que HDDs da época do Netezza
      GPUs/ASICs modernos superam FPGAs em throughput de dados
```

O Yellowbrick usou hardware commodity moderno para chegar ao mesmo resultado sem precisar de FPGA proprietário.

## SingleStore = MemSQL

São exatamente a mesma coisa. **MemSQL foi renomeado para SingleStore em 2020.**

```
2011:  Empresa fundada como MemSQL
2020:  Renomeada para SingleStore (mesmo produto, mesmo código, nova marca)
```

O rebranding foi para distanciar da percepção de "só banco in-memory" — o produto evoluiu para muito mais.

**O diferencial do SingleStore no ecossistema HTAP:**

Diferente do Teradata (que é "HTAP no papel"), o SingleStore foi arquitetado para ser OLTP e OLAP simultaneamente de verdade — mantendo dois tipos de armazenamento internamente:

```
Row store    → otimizado para OLTP (INSERT/UPDATE rápido)
Column store → otimizado para OLAP (SELECT analítico rápido)
                   ↓
        mesma query decide qual usar automaticamente
```

## HTAP real vs HTAP no papel

| Banco | HTAP? | Na prática |
|---|---|---|
| Teradata | "HTAP" (marketing) | Primariamente OLAP — overhead MPP para 1 INSERT é desnecessário |
| SingleStore | HTAP real | Arquitetado para os dois desde o início (rowstore + columnstore) |
| TiDB | HTAP real | Row store (TiKV) + Column store (TiFlash) separados mas sincronizados |

---

# Mapa Completo do Ecossistema

```
OLTP (transações do dia a dia)
  → PostgreSQL, MySQL, SQL Server, Oracle

OLAP / DW (analytics em grandes volumes)
  ├── Cloud managed     → BigQuery, Redshift, Snowflake, Synapse
  ├── MPP enterprise    → Teradata, Vertica, Greenplum
  ├── MPP + hardware    → Netezza (FPGA), Yellowbrick (NVMe)
  ├── Colunar open-src  → ClickHouse, DuckDB, StarRocks, Doris
  └── In-memory         → Exasol, SAP HANA

HTAP (OLTP + OLAP simultâneo)
  → SingleStore (MemSQL), TiDB, YugabyteDB, OceanBase

Timeseries (dados contínuos com timestamp)
  → TimescaleDB, InfluxDB, QuestDB, kdb+, TDengine

Data Lakehouse (lake + warehouse unificados)
  → Delta Lake (Databricks), Apache Iceberg, Apache Hudi

Motores de query sobre Data Lakes
  → Trino, Spark SQL, Dremio, Apache Hive, Impala
```
