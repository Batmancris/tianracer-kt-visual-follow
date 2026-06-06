# START HERE — KT Follow

## This car

1. **Start**: `.\scripts\kt_start_follow_stack.ps1`
2. **Check**: `.\scripts\kt_check_follow_stack.ps1`
3. **Stop**: `.\scripts\kt_stop_follow_stack.ps1`
4. **Web**: open `tools\bear_overlay_prod.html`

## Defaults

- dry-run only
- `enable_control=false`
- no ground follow
- no nonzero ackermann publish

## Hover test

- Only mode that allows temporary `armed` state
- Requires explicit gate check first

## Old entry points

All `kt_demo_*.ps1` and `start_ros2_overlay.ps1` scripts have been deleted.
Do not search for them. Use the three scripts above.

## Board

```bash
ssh sunrise@10.138.249.241
bash /home/sunrise/kt_scripts/start_kt_follow_stack.sh
```
