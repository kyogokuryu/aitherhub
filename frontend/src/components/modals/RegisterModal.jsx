import Register from "../../pages/authPages/Register";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
  DialogTrigger,
} from "../ui/dialog";

export default function RegisterModal({
  trigger,
  open,
  onOpenChange,
  onSwitchToLogin,
}) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      {trigger ? <DialogTrigger asChild>{trigger}</DialogTrigger> : null}
      <DialogContent className="w-[92vw] max-w-[428px] md:w-[700px] md:h-[500px] md:max-w-none p-0 bg-white">
        <DialogTitle className="sr-only">Register</DialogTitle>
        <DialogDescription className="sr-only">Register dialog</DialogDescription>
        <div className="p-6 w-full h-full mr-[6px] bg-white rounded-[10px]">
          <Register
            onSuccess={() => onOpenChange?.(false)}
            onSwitchToLogin={onSwitchToLogin}
          />
        </div>
      </DialogContent>
    </Dialog>
  );
}
