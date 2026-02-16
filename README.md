# OConsensoImpossivel

CLI em Python para escolher o melhor fim de semana (sexta a domingo) para lua de mel, com base em:
- **hard constraints**: datas em que a pessoa realmente nao pode.
- **soft constraints**: datas em que a pessoa pode, mas nao e ideal.

O programa recebe um intervalo temporal (`min_date` e `max_date`), gera todos os fins de semana elegiveis e devolve as melhores opcoes com explicacao de pessoas potencialmente afetadas.

## Requisitos

- Python 3.11+.
- Ambiente virtual recomendado em `.venv`.
- Opcional: pacote `openai` para narrativa final com IA.

## Instalacao

Criar e ativar ambiente virtual:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Instalar dependencia opcional da OpenAI:

```bash
source .venv/bin/activate
pip install --index-url https://pypi.org/simple openai
```

## Execucao

Execucao base (texto):

```bash
source .venv/bin/activate
python main.py --input examples/input.sample.json --top-n 3
```

Saida em JSON:

```bash
source .venv/bin/activate
python main.py --input examples/input.sample.json --top-n 3 --output-format json
```

Narrativa opcional com OpenAI:

```bash
source .venv/bin/activate
python main.py \
  --input examples/input.sample.json \
  --top-n 3 \
  --include-openai-narrative \
  --openai-api-key "$OPENAI_API_KEY"
```

## Formato de input

Datas em formato ISO `YYYY-MM-DD`.

```json
{
  "min_date": "2026-05-01",
  "max_date": "2026-06-30",
  "people": [
    {
      "name": "Ana",
      "hard_constraints": [
        {
          "type": "interval",
          "start_date": "2026-05-22",
          "end_date": "2026-05-24"
        }
      ],
      "soft_constraints": [
        { "type": "date", "date": "2026-05-15" }
      ]
    }
  ]
}
```

### Tipos de constraint

- `type: "date"` -> uma data especifica.
- `type: "interval"` -> intervalo inclusivo entre `start_date` e `end_date`.

## Logica de otimizacao

1. Gerar todos os fins de semana sexta-sabado-domingo totalmente dentro de `[min_date, max_date]`.
2. Tentar modo **estrito**:
   - eliminar qualquer fim de semana com sobreposicao a qualquer hard constraint de qualquer pessoa.
   - ordenar os restantes por:
     - maximizar `fully_feasible_people_count` (pessoas sem soft overlap),
     - minimizar `affected_people_count`,
     - minimizar `total_soft_overlap_days`,
     - data mais cedo em caso de empate.
3. Se o modo estrito nao produzir nenhuma opcao, ativar modo **fallback hard**:
   - considerar novamente todos os fins de semana;
   - escolher primeiro os que afetam menos pessoas em hard constraints (`hard_affected_people_count`);
   - depois aplicar os criterios de soft constraints e desempate por data.

## Saida

Para cada opcao devolvida:
- datas do fim de semana,
- modo de selecao (`strict_hard` ou `fallback_hard`),
- score detalhado,
- pessoas afetadas por hard constraints,
- pessoas afetadas por soft constraints.

## Estrutura do projeto

- `main.py`: ponto de entrada da aplicacao.
- `src/weekend_picker/models.py`: modelos e validacao do input.
- `src/weekend_picker/candidates.py`: geracao dos fins de semana candidatos.
- `src/weekend_picker/optimizer.py`: avaliacao e ranking.
- `src/weekend_picker/reporting.py`: formatacao de output e narrativa OpenAI.
- `src/weekend_picker/cli.py`: argumentos da CLI e orquestracao.
- `examples/input.sample.json`: exemplo de input.