# Split Audio Tracks

Divide um arquivo de áudio (MP3 ou similar) em faixas individuais usando ffmpeg com detecção automática de silêncio. As faixas são salvas na mesma pasta do arquivo original com numeração sequencial (01, 02, ...).

## Argumento esperado

`$ARGUMENTS` representa o caminho completo do arquivo de áudio a ser dividido.

Exemplo: `C:\onias\musicas\Resolver\concerto.mp3`

## Passos

1. **Verificar ffmpeg**: checar se o `ffmpeg` está disponível no PATH ou em `C:\Users\*\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg*\**\bin\ffmpeg.exe`. Se não encontrar, instalar via `winget install --id Gyan.FFmpeg -e --accept-source-agreements --accept-package-agreements` e localizar o executável após instalação.

2. **Obter duração**: rodar `ffmpeg -i "<arquivo>"` e extrair a linha `Duration` para informar ao usuário o tempo total.

3. **Detectar silêncios**: executar em background:
   ```
   ffmpeg -i "<arquivo>" -af "silencedetect=noise=-40dB:d=1.5" -f null - 2>&1
   ```
   Aguardar conclusão e ler as linhas `silence_start` e `silence_end` do output.

4. **Calcular pontos de corte**: interpretar os silêncios como separadores entre faixas. Gaps mais longos (> 3s) são candidatos mais prováveis a transições entre músicas. A faixa começa no `silence_end` do gap anterior e termina no `silence_start` do próximo gap. O início da primeira faixa é `0` e o fim da última faixa é a duração total do arquivo.

5. **Apresentar pontos de corte ao usuário**: mostrar a lista de faixas detectadas com seus timestamps (HH:MM:SS) antes de executar o split, permitindo ao usuário confirmar ou ajustar.

6. **Executar o split**: para cada faixa, rodar:
   ```
   ffmpeg -i "<arquivo>" -ss <inicio> -to <fim> -c copy "<pasta_original>\<NN> - Track <NN>.mp3"
   ```
   Usar `-c copy` para não recodificar (rápido e sem perda de qualidade). Numerar com zero à esquerda (01, 02...).

7. **Confirmar**: listar os arquivos gerados com seus tamanhos.

## Restrições

- Sempre usar `-c copy` no split para preservar qualidade sem recodificação.
- Salvar na mesma pasta do arquivo original, nunca em outro diretório sem confirmar com o usuário.
- Se o ffmpeg não estiver no PATH após instalação via winget, localizar o `.exe` manualmente em `AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg*`.
- Para gravações ao vivo (shows, concertos), o silêncio entre faixas pode ser mascarado por aplausos — nesse caso, threshold de `-40dB` pode não detectar todos os cortes; informar o usuário e sugerir ajuste manual dos timestamps se necessário.
- Gaps de silêncio muito curtos (< 2s) dentro de uma mesma música (respirações, pausas dramáticas) devem ser ignorados como pontos de corte — preferir gaps ≥ 3s como divisores de faixas.
