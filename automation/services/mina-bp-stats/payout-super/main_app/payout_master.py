from payouts_calculate_one_address import main as calculate_main
from payouts_calculate_one_address import read_staking_json_list
from payouts_calculate_one_address import get_last_processed_epoch_from_audit as get_c_audit

from payouts_validate_one_address import main as v_main
from payouts_validate_one_address import get_last_processed_epoch_from_audit as get_v_audit
from payouts_validate_one_address import determine_slot_range_for_validation
import sys

if __name__ == "__main__":
    c_epoch = get_c_audit()
    v_epoch = get_v_audit('validation')
    last_epoch = 0
    if c_epoch > v_epoch:
        last_epoch = v_epoch
    else:
        last_epoch = c_epoch
    
    total_epoch_to_cover = 60
    if last_epoch>=0:
        end=0
        result = 0
        for count in range(last_epoch, total_epoch_to_cover):
            calculate_main(count, False)
            if count<60 :
                result = v_main(count, False)
    else:
        total_epoch_to_cover = last_epoch+1
    sys.exit(total_epoch_to_cover)
