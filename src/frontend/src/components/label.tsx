import { Chip, type ChipProps } from '@mui/material';
import { forwardRef } from 'react';

export type LabelProps = ChipProps;

export const Label = forwardRef<HTMLDivElement, LabelProps>(function Label(
  props,
  ref
) {
  return <Chip ref={ref} {...props} />;
});