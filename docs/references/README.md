# Archived references

Local copies of external sources the project depends on, kept in the repository so
that figures cited in the report remain checkable even if a link rots.

Only **open-access** material is archived here, for research use within this course
project. Anything paywalled stays a link.

| File | Citation | Used for |
|---|---|---|
| `ribeiro-figueiredo-2018-mcts-ataxx.pdf` | Ribeiro, L. and Figueiredo, D. R. *Performance of Monte Carlo Tree Search Algorithms when Playing the Game Ataxx.* ENIAC 2018, Sao Paulo. DOI [10.5753/eniac.2018.4423](https://doi.org/10.5753/eniac.2018.4423). Open access via [SBC OpenLib](https://sol.sbc.org.br/index.php/eniac/article/view/4423). | Measured Ataxx branching factors (see [`../games/ataxx.md`](../games/ataxx.md) section 5.2), and related work - it evaluates MCTS variants on Ataxx, the same question this project asks. **Not yet read in full.** |

## Status

- [ ] Read `ribeiro-figueiredo-2018-mcts-ataxx.pdf` end to end and pull its
      methodology and results into the report's related-work section. The figures
      currently cited come from its abstract and indexing metadata.

> Reading the PDF needs a text extractor; none is installed in the dev environment.
> `apt-get install poppler-utils` provides `pdftotext`.
