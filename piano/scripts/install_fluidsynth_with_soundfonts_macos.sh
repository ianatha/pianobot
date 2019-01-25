echo "Installing FluidSynth:"
brew install fluid-synth --with-libsndfile

echo "Installing sound fonts:"

TARGET_FILE="$HOME/Library/Audio/Sounds/Banks/fluid_r3_gm.sf2"
ARCHIVE_FILE="/tmp/fluid-soundfont.tar.gz"
EXTRACTED_DIR="/tmp/fluid-soundfont"
if [ ! -f ${TARGET_FILE} ]; then
  echo "Installing Fluid R3 GM ..."
  if [ ! -f ${ARCHIVE_FILE} ]; then
    wget 'https://ftp.osuosl.org/pub/musescore/soundfont/fluid-soundfont.tar.gz' -O ${ARCHIVE_FILE}
  fi
  mkdir -p ${EXTRACTED_DIR}
  tar -xzvf ${ARCHIVE_FILE} -C ${EXTRACTED_DIR}
  mv "${EXTRACTED_DIR}/FluidR3 GM2-2.SF2" ${TARGET_FILE}
  rm -r ${EXTRACTED_DIR}
else
  echo "Fluid R3 GM is up-to-date."
fi

mkdir -p ~/.fluidsynth
ln -sf ${TARGET_FILE} ~/.fluidsynth/default_sound_font.sf2

echo "Installed sound fonts:"
ls -lh ~/Library/Audio/Sounds/Banks/