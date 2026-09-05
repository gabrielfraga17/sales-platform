# Sales Platform

Plataforma de gerenciamento de vendas, catálogo de produtos e integração com serviços em nuvem (GCP).

## 📁 Estrutura do Projeto

```text
sales-platform/
├── README.md
├── requirements.txt
├── app/                        # Código-fonte da aplicação
├── docs/                       # Documentação e Registro de Decisões de Arquitetura (ADRs)
│   └── 01_arquitetura_decisoes.md
├── tasks/                      # Tarefas e especificações funcionais
│   └── TASK-0001_catalogo.md
└── tests/                      # Testes automatizados (unitários e integração)
```

## 🛠️ Tecnologias e Infraestrutura

- **Linguagem**: Python 3.11+
- **Nuvem**: Google Cloud Platform (GCP)
- **Banco de Dados**: Firestore / Cloud SQL
- **Armazenamento**: Cloud Storage (GCS)
- **Framework Web**: FastAPI / Flask / Streamlit (a definir)

## 🚀 Como Executar

### Pré-requisitos
- Python 3.11+
- Google Cloud SDK (`gcloud`) autenticado

### Configuração do Ambiente Virtual
```bash
python -m venv .venv
# Windows (PowerShell)
.\.venv\Scripts\Activate.ps1

pip install -r requirements.txt
```
