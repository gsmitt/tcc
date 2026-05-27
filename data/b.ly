\version "2.18.2"
\include "lilypond-book-preamble.ly"

\paper {
  indent = 2\mm
  line-width = 210\mm
}

\layout {
  indent = #0
  \context {
    \Score
    \remove "Bar_number_engraver"
  }
}

music = \relative c'
{
  <a b c>
  <a b c>
}

\score{
  \music
  \layout{}
  \midi{}
}