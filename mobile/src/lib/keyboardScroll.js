// ============================================================================
// Hook clavier : garde les champs de saisie visibles au-dessus du clavier.
// ---------------------------------------------------------------------------
// Sur Android (edge-to-edge / adjustResize), KeyboardAvoidingView seul ne
// remonte pas toujours le champ focus — le clavier peut masquer la saisie.
// On mesure le champ focus puis on fait défiler le ScrollView du montant
// exact pour le placer juste au-dessus du clavier.
// ============================================================================
import { useCallback, useEffect, useRef, useState } from 'react';
import { Dimensions, Keyboard, Platform } from 'react-native';

/** Marge (px) laissee sous le champ focus au-dessus du clavier. */
const BOTTOM_GAP = 24;

/**
 * @returns {{
 *   scrollRef: import('react').MutableRefObject<any>,
 *   keyboardHeight: number,
 *   onScroll: (e: any) => void,
 *   scrollToField: (ref: import('react').MutableRefObject<any>) => void,
 * }}
 */
export function useKeyboardScroll() {
  const scrollRef = useRef(null);
  // Hauteur courante du clavier (ref = toujours a jour dans les callbacks).
  const kbRef = useRef(0);
  // Offset de scroll courant (en px) — lu dans scrollToField, mis a jour par onScroll.
  const scrollYRef = useRef(0);
  const [keyboardHeight, setKeyboardHeight] = useState(0);

  useEffect(() => {
    const showEvt = Platform.OS === 'ios' ? 'keyboardWillShow' : 'keyboardDidShow';
    const hideEvt = Platform.OS === 'ios' ? 'keyboardWillHide' : 'keyboardDidHide';
    const onShow = Keyboard.addListener(showEvt, (e) => {
      const h = e.endCoordinates?.height ?? 0;
      kbRef.current = h;
      setKeyboardHeight(h);
    });
    const onHide = Keyboard.addListener(hideEvt, () => {
      kbRef.current = 0;
      setKeyboardHeight(0);
    });
    return () => {
      onShow.remove();
      onHide.remove();
    };
  }, []);

  /**
   * A passer au ScrollView : memorise l'offset courant pour scrollToField.
   * @param {any} e event nativeEvent.contentOffset.y
   */
  const onScroll = useCallback((e) => {
    scrollYRef.current = e?.nativeEvent?.contentOffset?.y ?? 0;
  }, []);

  /**
   * A appeler depuis onFocus du champ : mesure sa position puis scroll le
   * ScrollView pour le placer juste au-dessus du clavier.
   * @param {import('react').MutableRefObject<any>} fieldRef ref du TextInput
   */
  const scrollToField = useCallback((fieldRef) => {
    // Petit delai : laisser le clavier s'ouvrir + le layout se stabiliser.
    const delay = Platform.OS === 'ios' ? 50 : 150;
    setTimeout(() => {
      const field = fieldRef?.current;
      const scroller = scrollRef.current;
      if (!field || !scroller) return;
      if (typeof field.measureInWindow !== 'function') return;

      field.measureInWindow((x, y, w, h) => {
        const kb = kbRef.current;
        if (kb <= 0) return; // clavier pas encore ouvert (ou deja ferme)

        const { height: screenH } = Dimensions.get('window');
        // Bas du champ (avec marge) compare au haut du clavier.
        const fieldBottom = y + h + BOTTOM_GAP;
        const keyboardTop = screenH - kb;
        const delta = fieldBottom - keyboardTop;
        if (delta > 0) {
          scroller.scrollTo({
            y: Math.max(0, scrollYRef.current + delta),
            animated: true,
          });
        }
      });
    }, delay);
  }, []);

  return { scrollRef, keyboardHeight, onScroll, scrollToField };
}
